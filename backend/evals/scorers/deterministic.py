"""Free output scorers encoding the product promises."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from agent.subgraphs.itinerary import RESTRICTION_KEYWORDS

_DESTINATIONS = {
    item["id"]: item
    for item in json.loads(
        (Path(__file__).resolve().parents[2] / "data" / "destinations.json").read_text(encoding="utf-8")
    )
}


def _result(passed: bool, detail: str, **metrics: Any) -> dict[str, Any]:
    return {"passed": passed, "detail": detail, **metrics}


def _haversine(a: dict, b: dict) -> float:
    lat1, lon1, lat2, lon2 = map(
        math.radians,
        [float(a["lat"]), float(a["lng"]), float(b["lat"]), float(b["lng"])],
    )
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def per_member_costs(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the cost components used by both scoring and blind labelling."""
    members = state.get("members") or []
    flights = state.get("flights") or []
    member_count = max(len(members), 1)
    hotel_share = float((state.get("hotel") or {}).get("total_price_usd", 0)) / member_count
    activity_share = (
        sum(float(day.get("estimated_day_cost_usd", 0)) for day in state.get("days", []))
        / member_count
    )
    costs: dict[str, dict[str, Any]] = {}
    for member in members:
        member_id = str(member.get("member_id") or member.get("email") or member.get("name"))
        member_flights = [
            flight
            for flight in flights
            if flight.get("member_id") == member.get("member_id")
        ]
        cheapest = min(
            member_flights,
            key=lambda flight: float(flight.get("price_usd", 0)),
            default=None,
        )
        flight_cost = float(cheapest.get("price_usd", 0)) if cheapest else 300.0
        budget = float(member["budget_usd"])
        total = flight_cost + hotel_share + activity_share
        costs[member_id] = {
            "member_id": member_id,
            "name": str(member.get("name") or member_id),
            "budget_usd": budget,
            "flight_usd": flight_cost,
            "flight_is_estimated": bool(cheapest.get("is_estimated")) if cheapest else True,
            "hotel_share_usd": hotel_share,
            "activity_share_usd": activity_share,
            "total_usd": total,
            "headroom_usd": budget - total,
            "utilization": total / budget,
            "fairness_utilization": (flight_cost + hotel_share) / budget,
        }
    return costs


def budget_metrics(state: dict[str, Any]) -> dict[str, Any]:
    costs = per_member_costs(state)
    full_utilization = {
        member_id: values["utilization"] for member_id, values in costs.items()
    }
    fairness_utilization = {
        member_id: values["fairness_utilization"] for member_id, values in costs.items()
    }
    spread = (
        max(fairness_utilization.values()) - min(fairness_utilization.values())
        if fairness_utilization
        else 0.0
    )
    return {
        "budget_compliance": _result(
            all(value <= 1 for value in full_utilization.values()),
            "Per-member cost includes cheapest flight, equal hotel share and equal itinerary-cost share.",
            utilization={key: round(value, 3) for key, value in full_utilization.items()},
        ),
        "fairness_spread": _result(
            spread <= 0.30,
            "Matches compute_fairness: maximum minus minimum budget utilization <= 0.30.",
            spread=round(spread, 3),
            utilization={
                key: round(value, 3) for key, value in fairness_utilization.items()
            },
        ),
    }


def dietary(state: dict[str, Any]) -> dict[str, Any]:
    restrictions = {
        restriction
        for member in state.get("members", [])
        for restriction in member.get("food_restrictions", [])
        if restriction in RESTRICTION_KEYWORDS
    }
    violations = []
    for day in state.get("days", []):
        meal_text = " ".join(str(meal).lower() for meal in day.get("meals", []))
        for restriction in restrictions:
            text_to_check = meal_text
            if restriction in {"vegetarian", "vegan"}:
                qualifier = restriction
                for word in RESTRICTION_KEYWORDS[restriction]:
                    text_to_check = re.sub(
                        rf"\b{qualifier}\s+{re.escape(word)}\b",
                        "",
                        text_to_check,
                    )
            if restriction == "vegan":
                text_to_check = re.sub(
                    r"\b(?:dairy|egg)[- ]free\s+(?:cheese|milk|egg)\b",
                    "",
                    text_to_check,
                )
            if restriction == "gluten_free":
                text_to_check = re.sub(
                    r"\bgluten[- ]free\s+(?:pasta|bread|flour|wheat)\b",
                    "",
                    text_to_check,
                )
                text_to_check = re.sub(
                    r"\b(?:pasta|bread|flour|wheat)[- ]free\b",
                    "",
                    text_to_check,
                )
            found = [
                word
                for word in RESTRICTION_KEYWORDS[restriction]
                if re.search(rf"\b{re.escape(word)}\b", text_to_check)
            ]
            if found:
                violations.append({"day": day.get("day_number"), "restriction": restriction, "terms": found})
    return _result(not violations, "Meal text contains no prohibited validator keywords.", violations=violations)


def hard_avoids(state: dict[str, Any]) -> dict[str, Any]:
    constraints = state.get("preference_constraints") or {}
    terms = {
        str(term).lower()
        for term in constraints.get("activity_filters", {}).get("avoid_tags", [])
        if str(term).strip()
    }
    for constraint in constraints.get("hard_constraints", []):
        if constraint.get("type") == "avoid":
            terms.add(str(constraint.get("target", "")).lower())
            raw = constraint.get("terms", [])
            terms.update(str(item).lower() for item in ([raw] if isinstance(raw, str) else raw))
    violations = []
    for day in state.get("days", []):
        for activity in day.get("activities", []):
            text = " ".join(
                [str(activity.get("name", "")), str(activity.get("category", ""))]
                + [str(tag) for tag in activity.get("tags", [])]
            ).lower()
            matched = [term for term in terms if term and term in text]
            if matched:
                violations.append({"activity": activity.get("name"), "terms": matched})
    return _result(not violations, "Activities do not match extracted hard-avoid terms.", violations=violations)


def dates(state: dict[str, Any]) -> dict[str, Any]:
    start = datetime.fromisoformat(state["start_date"]).date()
    expected_count = int(state.get("trip_duration_days") or (datetime.fromisoformat(state["end_date"]).date() - start).days)
    actual = [datetime.fromisoformat(day["date"]).date() for day in state.get("days", [])]
    expected = [start + timedelta(days=index) for index in range(expected_count)]
    return _result(actual == expected, "Day dates must be contiguous and match trip_duration_days.")


def radius(state: dict[str, Any]) -> dict[str, Any]:
    selected = next(
        (
            item
            for item in state.get("candidate_destinations", [])
            if item.get("name") == state.get("selected_destination")
        ),
        {},
    )
    destination = _DESTINATIONS.get(str(selected.get("id", "")))
    if not destination:
        return _result(False, "Selected destination could not be joined to destinations.json.")
    center = {"lat": destination["lat"], "lng": destination["lng"]}
    limit = float(destination["search_radius_km"])
    outside = []
    for day in state.get("days", []):
        for activity in day.get("activities", []):
            distance = _haversine(center, activity)
            if distance > limit:
                outside.append({"activity": activity.get("name"), "distance_km": round(distance, 2)})
    return _result(
        not outside,
        "Scored against destinations.json radius; Places fetch itself uses a fixed 20 km radius.",
        search_radius_km=limit,
        outside=outside,
    )


def geographic_plausibility(state: dict[str, Any]) -> dict[str, Any]:
    implausible = []
    for day in state.get("days", []):
        activities = day.get("activities", [])
        for first, second in zip(activities, activities[1:]):
            distance = _haversine(first, second)
            if distance > 50:
                implausible.append(
                    {"day": day.get("day_number"), "from": first.get("name"), "to": second.get("name"), "km": round(distance, 2)}
                )
    return _result(not implausible, "Consecutive activities must be no more than 50 km apart.", legs=implausible)


def flight_alignment(state: dict[str, Any]) -> dict[str, Any]:
    days = state.get("days") or []
    if not days:
        return _result(False, "No days to align.", scorable=False)
    flights = state.get("flights", [])
    if not flights or any(flight.get("is_estimated") for flight in flights):
        return _result(
            False,
            "Estimated flights do not carry trustworthy arrival/departure times.",
            scorable=False,
        )
    arrivals = [
        datetime.fromisoformat(str(flight["arrival_time"]).replace(" ", "T"))
        for flight in flights
        if flight.get("arrival_time")
    ]
    departures = [
        datetime.fromisoformat(str(flight["return_departure_time"]).replace(" ", "T"))
        for flight in flights
        if flight.get("return_departure_time")
    ]
    first_schedule = days[0].get("schedule") or []
    last_schedule = days[-1].get("schedule") or []
    if not arrivals or not departures or not first_schedule or not last_schedule:
        return _result(
            False,
            "Flight schema lacks destination arrival and return-departure timestamps.",
            scorable=False,
        )

    def schedule_time(value: Any) -> time:
        for fmt in ("%H:%M", "%I:%M %p", "%I %p"):
            try:
                return datetime.strptime(str(value), fmt).time()
            except ValueError:
                continue
        raise ValueError(f"Unsupported schedule time {value!r}")

    first_time = datetime.combine(max(arrivals).date(), schedule_time(first_schedule[0]["time"]))
    last_time = datetime.combine(min(departures).date(), schedule_time(last_schedule[-1]["time"]))
    return _result(
        first_time >= max(arrivals) and last_time <= min(departures),
        "First scheduled item follows latest arrival; final item precedes earliest departure.",
        scorable=True,
    )


def schema_complete(state: dict[str, Any]) -> dict[str, Any]:
    missing = [
        field
        for field in ("days", "trip_pitch", "constraint_satisfaction", "fairness_scores")
        if not state.get(field)
    ]
    return _result(not missing, "Required output fields are present and non-empty.", missing=missing)


def _safe_score(name: str, scorer: Any, state: dict[str, Any]) -> dict[str, Any]:
    try:
        return scorer(state)
    except Exception as exc:  # malformed product output is a failed score, not a broken eval run
        return _result(False, f"{name} could not evaluate the output: {type(exc).__name__}: {exc}")


def score_all(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    budgets = _safe_score("budget", budget_metrics, state)
    if "passed" in budgets:
        budget_results = {
            "budget_compliance": budgets,
            "fairness_spread": budgets,
        }
    else:
        budget_results = budgets
    return {
        **budget_results,
        "dietary": _safe_score("dietary", dietary, state),
        "hard_avoids": _safe_score("hard_avoids", hard_avoids, state),
        "dates": _safe_score("dates", dates, state),
        "radius": _safe_score("radius", radius, state),
        "geographic_plausibility": _safe_score(
            "geographic_plausibility",
            geographic_plausibility,
            state,
        ),
        "flight_alignment": _safe_score("flight_alignment", flight_alignment, state),
        "schema_complete": _safe_score("schema_complete", schema_complete, state),
    }
