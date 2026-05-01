"""Full itinerary agent subgraph."""

import json
import logging
import math
import re
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from langgraph.graph import END, StateGraph

from agent.state import ActivityResult, DayPlan, DecisionLogEntry, ItineraryState, MemberInput
from config import get_llm
from tools.google_routes import plan_day_routes

logger = logging.getLogger(__name__)

PREFERENCE_DIMENSIONS = ("outdoor", "food", "nightlife", "urban", "shopping")
CLUSTER_RADIUS_KM = 1.5

RESTRICTION_KEYWORDS = {
    "vegetarian": ["beef", "chicken", "pork", "meat", "bacon", "steak"],
    "vegan": ["beef", "chicken", "pork", "meat", "bacon", "steak", "cheese", "dairy", "milk", "egg"],
    "halal": ["pork", "bacon", "ham", "lard"],
    "gluten_free": ["pasta", "bread", "flour", "wheat"],
}


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(d_lng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _decision(node: str, decision: str, reason: str) -> DecisionLogEntry:
    return DecisionLogEntry(
        node=node,
        decision=decision,
        reason=reason,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _message_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "".join(str(part.get("text", part)) if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    if not cleaned.startswith("[") and "[" in cleaned and "]" in cleaned:
        cleaned = cleaned[cleaned.find("[") : cleaned.rfind("]") + 1]
    return cleaned


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    iso_candidate = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate)
    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    logger.warning("Could not parse flight datetime: %s", raw)
    return None


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _date_for_day(start_date: str, day_number: int) -> str:
    parsed = _parse_date(start_date)
    if not parsed:
        return start_date
    return (parsed + timedelta(days=max(day_number - 1, 0))).isoformat()


def _activity_coords(activity: ActivityResult) -> tuple[float, float]:
    return float(activity.get("lat", 0.0)), float(activity.get("lng", 0.0))


def _cluster_center(activities: list[ActivityResult], fallback: dict) -> tuple[float, float]:
    if not activities:
        return float(fallback.get("lat", 0.0)), float(fallback.get("lng", 0.0))
    lat = sum(float(activity.get("lat", 0.0)) for activity in activities) / len(activities)
    lng = sum(float(activity.get("lng", 0.0)) for activity in activities) / len(activities)
    return lat, lng


def _neighborhood_name(activity: ActivityResult | None, destination: str) -> str:
    if activity:
        address = str(activity.get("address", "")).strip()
        if address:
            return address.split(",", 1)[0].strip() or f"Central {destination}"
    return f"Central {destination}"


def _to_cluster(center: ActivityResult | None, activities: list[ActivityResult], state: ItineraryState) -> dict:
    center_lat, center_lng = _cluster_center(activities, state.get("destination_coords", {}))
    return {
        "day": 0,
        "neighborhood": _neighborhood_name(center, state["destination"]),
        "center_lat": center_lat,
        "center_lng": center_lng,
        "activities": activities,
    }


def _merge_smallest_clusters(clusters: list[dict], target_count: int) -> list[dict]:
    clusters = deepcopy(clusters)
    while len(clusters) > target_count:
        smallest_idx = min(range(len(clusters)), key=lambda idx: len(clusters[idx].get("activities", [])))
        smallest = clusters.pop(smallest_idx)
        nearest_idx = min(
            range(len(clusters)),
            key=lambda idx: haversine_km(
                float(smallest.get("center_lat", 0.0)),
                float(smallest.get("center_lng", 0.0)),
                float(clusters[idx].get("center_lat", 0.0)),
                float(clusters[idx].get("center_lng", 0.0)),
            ),
        )
        clusters[nearest_idx]["activities"].extend(smallest.get("activities", []))
        center_lat, center_lng = _cluster_center(clusters[nearest_idx]["activities"], {})
        clusters[nearest_idx]["center_lat"] = center_lat
        clusters[nearest_idx]["center_lng"] = center_lng
    return clusters


def _expand_clusters_to_days(clusters: list[dict], target_count: int) -> list[dict]:
    clusters = deepcopy(clusters)
    while len(clusters) < target_count and clusters:
        largest = max(clusters, key=lambda cluster: len(cluster.get("activities", [])))
        clusters.append(deepcopy(largest))
    return clusters


def _group_preference_vector(members: list[MemberInput]) -> dict[str, float]:
    if not members:
        return {dimension: 0.0 for dimension in PREFERENCE_DIMENSIONS}
    return {
        dimension: sum(float(member.get("preference_vector", {}).get(dimension, 0.0)) for member in members)
        / len(members)
        for dimension in PREFERENCE_DIMENSIONS
    }


def _food_restrictions(members: list[MemberInput]) -> list[str]:
    restrictions: set[str] = set()
    for member in members:
        for restriction in member.get("food_restrictions", []):
            value = str(restriction).strip()
            if value:
                restrictions.add(value)
    return sorted(restrictions)


def _normalize_restriction(restriction: str) -> str:
    return restriction.strip().lower().replace("-", "_").replace(" ", "_")


def _restriction_keywords(members: list[MemberInput]) -> set[str]:
    keywords: set[str] = set()
    for restriction in _food_restrictions(members):
        keywords.update(RESTRICTION_KEYWORDS.get(_normalize_restriction(restriction), []))
    return keywords


def _constraints(state: ItineraryState) -> dict:
    return state.get("preference_constraints") or {}


def _constraint_avoid_terms(preference_constraints: dict) -> set[str]:
    terms = {
        str(term).lower()
        for term in preference_constraints.get("activity_filters", {}).get("avoid_tags", [])
        if str(term).strip()
    }
    for constraint in preference_constraints.get("hard_constraints", []):
        if not isinstance(constraint, dict) or constraint.get("type") != "avoid":
            continue
        terms.add(str(constraint.get("target", "")).lower())
        raw_terms = constraint.get("terms", [])
        if isinstance(raw_terms, str):
            raw_terms = [raw_terms]
        terms.update(str(term).lower() for term in raw_terms if str(term).strip())
    return {term for term in terms if term}


def _meal_requirements(preference_constraints: dict) -> list[dict]:
    return [
        requirement
        for requirement in preference_constraints.get("meal_requirements", {}).get("must_include", [])
        if isinstance(requirement, dict) and requirement.get("cuisine")
    ]


def _schedule_constraints(preference_constraints: dict) -> dict:
    schedule = preference_constraints.get("schedule", {})
    return schedule if isinstance(schedule, dict) else {}


def _pace(preference_constraints: dict) -> str:
    return str(_schedule_constraints(preference_constraints).get("pace") or "balanced").lower()


def _activity_count_rule(preference_constraints: dict) -> str:
    pace = _pace(preference_constraints)
    if pace == "relaxed":
        return "Each day gets 2-3 activities from that day's cluster when available."
    if pace == "packed":
        return "Each day gets 4-6 activities from that day's cluster when available."
    return "Each day gets 3-5 activities from that day's cluster when available."


def _earliest_start_time(preference_constraints: dict) -> time | None:
    schedule = _schedule_constraints(preference_constraints)
    raw_value = schedule.get("earliest_start_time")
    if not raw_value and schedule.get("avoid_early_mornings"):
        raw_value = "10:00"
    if not raw_value:
        return None
    try:
        hour, minute = str(raw_value).split(":", 1)
        return time(int(hour), int(minute[:2]))
    except (TypeError, ValueError):
        return None


def _activity_matches_terms(activity: dict, terms: set[str]) -> bool:
    if not terms:
        return False
    haystack = " ".join(
        [
            str(activity.get("name", "")),
            str(activity.get("category", "")),
            " ".join(str(tag) for tag in activity.get("tags", [])),
        ]
    ).lower()
    return any(term in haystack for term in terms)


def _parse_schedule_time(raw_value: Any) -> time | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    for fmt in ("%H:%M", "%I:%M %p", "%I %p"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def _constraint_satisfaction_report(
    preference_constraints: dict,
    satisfied: list[str],
    unmet: list[str],
    warnings: list[str] | None = None,
) -> dict:
    has_constraints = bool(
        preference_constraints.get("hard_constraints")
        or preference_constraints.get("meal_requirements", {}).get("must_include")
        or preference_constraints.get("schedule", {}).get("avoid_early_mornings")
        or preference_constraints.get("schedule", {}).get("pace") not in (None, "", "balanced")
        or preference_constraints.get("activity_filters", {}).get("avoid_tags")
    )
    if not preference_constraints or not has_constraints:
        return {
            "passed": True,
            "satisfied": ["No natural-language hard constraints supplied"],
            "unmet": [],
            "warnings": warnings or [],
        }

    return {
        "passed": not unmet,
        "satisfied": satisfied,
        "unmet": unmet,
        "warnings": warnings or [],
    }


def _activities_prompt_summary(clusters: list[dict]) -> str:
    lines: list[str] = []
    for cluster in sorted(clusters, key=lambda item: int(item.get("day", 0))):
        activity_lines = [
            f"- {activity.get('name', 'Unnamed activity')} ({activity.get('category', 'activity')})"
            for activity in cluster.get("activities", [])
        ]
        if not activity_lines:
            activity_lines = ["- No matched activities available"]
        lines.append(
            f"Day {cluster.get('day')}: {cluster.get('neighborhood', 'Central')}\n"
            + "\n".join(activity_lines)
        )
    return "\n\n".join(lines)


def _normalize_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _activity_lookup(activities: list[ActivityResult]) -> dict[str, ActivityResult]:
    return {_normalize_name(activity.get("name", "")): activity for activity in activities if activity.get("name")}


def _match_activity_by_name(name: str, activities: list[ActivityResult], lookup: dict[str, ActivityResult]) -> ActivityResult | None:
    normalized = _normalize_name(name)
    if normalized in lookup:
        return lookup[normalized]

    for activity in activities:
        activity_name = _normalize_name(activity.get("name", ""))
        if activity_name and (activity_name in normalized or normalized in activity_name):
            return activity
    return None


def _coerce_activity_names(raw_activities: Any) -> list[str]:
    if not isinstance(raw_activities, list):
        return []
    names: list[str] = []
    for activity in raw_activities:
        if isinstance(activity, dict):
            name = activity.get("name")
        else:
            name = activity
        if name:
            names.append(str(name))
    return names


def _coerce_meals(raw_meals: Any) -> list[str]:
    if not isinstance(raw_meals, list):
        return []
    return [str(meal) for meal in raw_meals if meal]


def _coerce_schedule(raw_schedule: Any) -> list[dict]:
    if not isinstance(raw_schedule, list):
        return []
    entries: list[dict] = []
    for entry in raw_schedule:
        if not isinstance(entry, dict):
            continue
        entries.append(
            {
                "time": str(entry.get("time") or "").strip(),
                "type": str(entry.get("type") or "").strip().lower(),
                "label": str(entry.get("label") or entry.get("activity") or entry.get("meal") or "").strip(),
                "notes": str(entry.get("notes") or "").strip(),
            }
        )
    return entries


def _coerce_constraint_notes(raw_notes: Any) -> list[str]:
    if isinstance(raw_notes, str):
        raw_notes = [raw_notes]
    if not isinstance(raw_notes, list):
        return []
    return [str(note).strip() for note in raw_notes if str(note).strip()]


def _fallback_rationale(raw: dict, state: ItineraryState) -> str:
    neighborhood = str(raw.get("neighborhood") or f"Central {state['destination']}")
    return (
        f"Planned around {neighborhood} to keep the day's activities geographically grouped, "
        "reduce travel time, and reflect the group's stated preferences."
    )


def _fallback_constraint_notes(state: ItineraryState) -> list[str]:
    notes: list[str] = []
    preference_constraints = _constraints(state)
    schedule = _schedule_constraints(preference_constraints)

    if schedule.get("avoid_early_mornings"):
        notes.append(
            f"Starts non-breakfast items no earlier than {schedule.get('earliest_start_time') or '10:00'}."
        )
    if _pace(preference_constraints) != "balanced":
        notes.append(f"Uses a {_pace(preference_constraints)} pace.")
    avoid_terms = sorted(_constraint_avoid_terms(preference_constraints))
    if avoid_terms:
        notes.append(f"Avoids requested activity terms: {', '.join(avoid_terms[:6])}.")
    for requirement in _meal_requirements(preference_constraints):
        cuisine = str(requirement.get("cuisine", "")).strip()
        if cuisine:
            notes.append(f"Accounts for requested {cuisine} meal coverage.")
    restrictions = _food_restrictions(state.get("members", []))
    if restrictions:
        notes.append(f"Respects food restrictions: {', '.join(restrictions)}.")
    return notes


def _coerce_day_plan(raw: dict, index: int, state: ItineraryState) -> DayPlan:
    day_number = int(raw.get("day_number") or index + 1)
    return DayPlan(
        day_number=day_number,
        date=str(raw.get("date") or _date_for_day(state["start_date"], day_number)),
        neighborhood=str(raw.get("neighborhood") or f"Central {state['destination']}"),
        activities=_coerce_activity_names(raw.get("activities")),  # type: ignore[arg-type]
        meals=_coerce_meals(raw.get("meals")),
        routes=[],
        estimated_day_cost_usd=float(raw.get("estimated_day_cost_usd") or 0.0),
        schedule=_coerce_schedule(raw.get("schedule")),
        rationale=str(raw.get("rationale") or _fallback_rationale(raw, state)).strip(),
        constraint_notes=_coerce_constraint_notes(raw.get("constraint_notes"))
        or _fallback_constraint_notes(state),
    )


async def cluster_by_neighborhood(state: ItineraryState) -> dict:
    unassigned = list(state.get("activities", []))
    raw_clusters: list[dict] = []

    while unassigned:
        center = unassigned.pop(0)
        center_lat, center_lng = _activity_coords(center)
        cluster_activities = [center]
        still_unassigned: list[ActivityResult] = []

        for activity in unassigned:
            lat, lng = _activity_coords(activity)
            if haversine_km(center_lat, center_lng, lat, lng) <= CLUSTER_RADIUS_KM:
                cluster_activities.append(activity)
            else:
                still_unassigned.append(activity)

        raw_clusters.append(_to_cluster(center, cluster_activities, state))
        unassigned = still_unassigned

    day_count = max(int(state.get("trip_duration_days") or 1), 1)
    if not raw_clusters:
        fallback_cluster = _to_cluster(None, [], state)
        raw_clusters = [fallback_cluster]

    if len(raw_clusters) > day_count:
        raw_clusters = _merge_smallest_clusters(raw_clusters, day_count)
    elif len(raw_clusters) < day_count:
        raw_clusters = _expand_clusters_to_days(raw_clusters, day_count)

    clustered_activities = []
    for index, cluster in enumerate(raw_clusters[:day_count], start=1):
        clustered_activities.append({**cluster, "day": index})

    return {
        "clustered_activities": clustered_activities,
        "decision_log": [
            _decision(
                "cluster_by_neighborhood",
                f"Grouped activities into {len(clustered_activities)} day clusters",
                f"Started with {len(state.get('activities', []))} activities across {day_count} days",
            )
        ],
    }


async def build_itinerary(state: ItineraryState) -> dict:
    validation_rebuild_count = int(state.get("validation_rebuild_count") or 0)
    is_retry = bool(state.get("days")) or bool(state.get("validation_errors"))
    if is_retry:
        validation_rebuild_count += 1

    hotel = state.get("hotel") or {}
    weather = state.get("weather") or {}
    food_restrictions = _food_restrictions(state.get("members", []))
    preference_vector = _group_preference_vector(state.get("members", []))
    preference_constraints = _constraints(state)
    validation_errors = state.get("validation_errors", [])

    prompt = (
        "Build a practical day-by-day group trip itinerary from the provided activity clusters.\n"
        "Return ONLY a JSON array of DayPlan objects, no markdown, no backticks.\n"
        "Each DayPlan must use this shape: {day_number: int, date: str (ISO), neighborhood: str, "
        "activities: [list of activity names as strings], meals: [exactly 3 strings: breakfast, lunch, dinner], "
        "schedule: [objects with time, type, label, notes], estimated_day_cost_usd: float, "
        "rationale: str, constraint_notes: [short strings]}.\n\n"
        "Rules:\n"
        f"- {_activity_count_rule(preference_constraints)}\n"
        "- Breakfast is always at or near the hotel.\n"
        "- Lunch and dinner reference real neighborhood options.\n"
        "- Do not violate any listed food restrictions in any meal.\n"
        "- Treat hard_constraints, activity_filters, schedule constraints, and meal_requirements as non-negotiable.\n"
        "- If schedule.avoid_early_mornings is true, do not schedule non-breakfast items before earliest_start_time.\n"
        "- If meal_requirements.must_include lists a cuisine, include it in at least that many meal strings.\n"
        "- Schedule entries must use HH:MM 24-hour time and label the matching meal or activity.\n"
        "- rationale explains why this day's neighborhood, activities, pacing, and meals fit the group.\n"
        "- constraint_notes names the concrete constraints this day respects, such as no clubs, late starts, pace, cuisine, or food restrictions.\n"
        "- estimated_day_cost_usd is a realistic estimate per person multiplied by number of members.\n"
        "- Use the provided ISO dates in order.\n\n"
        f"Destination: {state['destination']}\n"
        f"Trip dates: {state['start_date']} to {state['end_date']}\n"
        f"Trip duration days: {state['trip_duration_days']}\n"
        f"Hotel: {hotel.get('name', 'Hotel TBD')}, {hotel.get('address', state['destination'])}\n"
        f"Weather summary: {weather.get('summary', 'Unavailable')}\n"
        f"Food restrictions: {json.dumps(food_restrictions)}\n"
        f"Group preference vector: {json.dumps(preference_vector)}\n"
        f"Group notes: {json.dumps(state.get('group_notes', ''))}\n"
        f"Preference constraints: {json.dumps(preference_constraints)}\n"
        f"Group size: {len(state.get('members', []))}\n"
        f"Previous validation errors to fix: {json.dumps(validation_errors)}\n\n"
        f"Activity clusters by day:\n{_activities_prompt_summary(state.get('clustered_activities', []))}"
    )

    try:
        response = await get_llm().ainvoke(prompt)
        cleaned = _strip_json_fences(_message_text(response))
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and isinstance(parsed.get("days"), list):
            parsed = parsed["days"]
        if not isinstance(parsed, list):
            raise ValueError("LLM response was not a JSON array.")
    except Exception as exc:  # noqa: BLE001
        logger.error("build_itinerary parse error: %s", exc)
        return {
            "days": state.get("days", []),
            "validation_rebuild_count": validation_rebuild_count,
            "decision_log": [
                _decision(
                    "build_itinerary",
                    "Itinerary JSON parse failed",
                    f"Preserved {len(state.get('days', []))} existing days: {exc}",
                )
            ],
        }

    days = [
        _coerce_day_plan(raw_day, index, state)
        for index, raw_day in enumerate(parsed)
        if isinstance(raw_day, dict)
    ]

    return {
        "days": days,
        "validation_rebuild_count": validation_rebuild_count,
        "decision_log": [
            _decision(
                "build_itinerary",
                f"Built {len(days)} itinerary days",
                f"Retry count: {validation_rebuild_count}",
            )
        ],
    }


async def align_flight_times(state: ItineraryState) -> dict:
    days = deepcopy(state.get("days", []))
    flights = state.get("flights", [])
    if not flights or not days:
        return {
            "days": days,
            "decision_log": [
                _decision(
                    "align_flight_times",
                    "Flight alignment skipped",
                    "No flights or no days available",
                )
            ],
        }

    depart_times = [
        parsed for parsed in (_parse_datetime(flight.get("depart_time")) for flight in flights) if parsed is not None
    ]
    return_times = [
        parsed for parsed in (_parse_datetime(flight.get("return_time")) for flight in flights) if parsed is not None
    ]

    notes: list[str] = []
    if depart_times:
        latest_arrival_buffered = max(depart_times) + timedelta(hours=1.5)
        if latest_arrival_buffered.time() >= time(12, 0):
            first_day = min(days, key=lambda day: int(day.get("day_number", 1)))
            first_day["activities"] = list(first_day.get("activities", []))[:3]
            notes.append("capped day 1 at 3 activities")

    if return_times:
        earliest_departure_cutoff = min(return_times) - timedelta(hours=2.5)
        if earliest_departure_cutoff.time() < time(17, 0):
            last_day = max(days, key=lambda day: int(day.get("day_number", 1)))
            last_day["activities"] = list(last_day.get("activities", []))[:2]
            notes.append("capped final day at 2 activities")

    return {
        "days": days,
        "decision_log": [
            _decision(
                "align_flight_times",
                "Aligned itinerary with flight windows",
                ", ".join(notes) if notes else "No activity trimming needed",
            )
        ],
    }


async def plan_routes(state: ItineraryState) -> dict:
    days = deepcopy(state.get("days", []))
    activities = state.get("activities", [])
    lookup = _activity_lookup(activities)
    skipped_names = 0
    total_travel_minutes = 0

    for day in days:
        matched_activities: list[ActivityResult] = []
        raw_day_activities = day.get("activities", [])

        for activity in raw_day_activities:
            if isinstance(activity, dict) and "lat" in activity and "lng" in activity:
                matched_activities.append(activity)  # type: ignore[arg-type]
                continue

            name = activity.get("name") if isinstance(activity, dict) else activity
            matched = _match_activity_by_name(str(name), activities, lookup) if name else None
            if matched:
                matched_activities.append(matched)
            else:
                skipped_names += 1

        if len(matched_activities) >= 2:
            route_result = await plan_day_routes(matched_activities)
            day["routes"] = route_result.get("routes", [])
            day["total_travel_minutes"] = int(route_result.get("total_travel_minutes", 0))
        else:
            day["routes"] = []
            day["total_travel_minutes"] = 0

        day["activities"] = matched_activities
        total_travel_minutes += int(day.get("total_travel_minutes", 0))

    return {
        "days": days,
        "decision_log": [
            _decision(
                "plan_routes",
                f"Planned routes for {len(days)} days",
                f"{total_travel_minutes} total travel minutes; skipped {skipped_names} unmatched activities",
            )
        ],
    }


def check_feasibility(state: ItineraryState) -> str:
    for day in state.get("days", []):
        if int(day.get("total_travel_minutes", 0)) <= 180:
            continue

        if int(state.get("feasibility_swap_count") or 0) >= 2:
            continue

        activities = list(day.get("activities", []))
        if len(activities) <= 1:
            continue

        activities.pop()
        day["activities"] = activities
        state["feasibility_swap_count"] = int(state.get("feasibility_swap_count") or 0) + 1
        return "swap"

    return "pass"


async def validation_gate(state: ItineraryState) -> dict:
    errors: list[str] = []
    constraint_unmet: list[str] = []
    constraint_satisfied: list[str] = []
    constraint_warnings: list[str] = []
    days = state.get("days", [])
    preference_constraints = _constraints(state)

    for day in days:
        day_number = day.get("day_number", "?")
        meals = day.get("meals", [])
        if len(meals) != 3:
            errors.append(f"Day {day_number} has {len(meals)} meals instead of exactly 3.")
        if len(day.get("activities", [])) == 0:
            errors.append(f"Day {day_number} has no activities.")

    keywords = _restriction_keywords(state.get("members", []))
    for day in days:
        for meal in day.get("meals", []):
            meal_lower = str(meal).lower()
            for keyword in keywords:
                if keyword in meal_lower:
                    errors.append(
                        f"Day {day.get('day_number', '?')} meal violates food restriction keyword: {keyword}."
                    )

    avoid_terms = _constraint_avoid_terms(preference_constraints)
    if avoid_terms:
        avoid_violations = []
        for day in days:
            for activity in day.get("activities", []):
                if isinstance(activity, dict) and _activity_matches_terms(activity, avoid_terms):
                    avoid_violations.append(
                        f"Day {day.get('day_number', '?')} includes avoided activity: {activity.get('name')}"
                    )
        if avoid_violations:
            constraint_unmet.extend(avoid_violations)
        else:
            constraint_satisfied.append("Avoided activity categories and terms were not scheduled.")

    all_meals_text = " | ".join(str(meal).lower() for day in days for meal in day.get("meals", []))
    for requirement in _meal_requirements(preference_constraints):
        cuisine = str(requirement.get("cuisine", "")).strip().lower()
        try:
            min_count = int(requirement.get("min_count") or 1)
        except (TypeError, ValueError):
            min_count = 1
        actual_count = all_meals_text.count(cuisine)
        if actual_count < min_count:
            constraint_unmet.append(
                f"Required cuisine '{cuisine}' appears {actual_count} times; expected at least {min_count}."
            )
        else:
            constraint_satisfied.append(
                f"Required cuisine '{cuisine}' appears {actual_count} times."
            )

    earliest = _earliest_start_time(preference_constraints)
    if earliest:
        schedule_missing = False
        early_items = []
        for day in days:
            schedule_entries = day.get("schedule", [])
            if not schedule_entries:
                schedule_missing = True
                continue
            for entry in schedule_entries:
                entry_type = str(entry.get("type", "")).lower()
                if entry_type == "breakfast":
                    continue
                parsed_time = _parse_schedule_time(entry.get("time"))
                if parsed_time and parsed_time < earliest:
                    early_items.append(
                        f"Day {day.get('day_number', '?')} schedules {entry.get('label', 'an item')} at {entry.get('time')}"
                    )
        if early_items:
            constraint_unmet.extend(early_items)
        elif schedule_missing:
            constraint_unmet.append("Schedule metadata is missing, so earliest-start constraints cannot be verified.")
        else:
            constraint_satisfied.append(f"No non-breakfast items start before {earliest.strftime('%H:%M')}.")

    if _pace(preference_constraints) == "relaxed":
        packed_days = [
            f"Day {day.get('day_number', '?')} has {len(day.get('activities', []))} activities"
            for day in days
            if len(day.get("activities", [])) > 3
        ]
        if packed_days:
            constraint_unmet.extend(packed_days)
        else:
            constraint_satisfied.append("Relaxed pace honored with no more than 3 activities per day.")

    errors.extend(constraint_unmet)

    members = state.get("members", [])
    avg_flight_cost = sum(float(flight.get("price_usd", 0.0)) for flight in state.get("flights", [])) / max(
        len(members), 1
    )
    hotel = state.get("hotel") or {}
    total_cost = (
        sum(float(day.get("estimated_day_cost_usd", 0.0)) for day in days)
        + float(hotel.get("total_price_usd", 0.0))
        + avg_flight_cost * len(members)
    )
    group_budget = sum(float(member.get("budget_usd", 0.0)) for member in members)
    if total_cost > group_budget * 1.15:
        errors.append(
            f"Estimated total cost ${total_cost:.0f} exceeds group budget buffer ${group_budget * 1.15:.0f}."
        )

    expected_days = int(state.get("trip_duration_days") or 0)
    if len(days) != expected_days:
        errors.append(f"Expected {expected_days} days, got {len(days)}.")

    return {
        "validation_errors": errors,
        "constraint_satisfaction": _constraint_satisfaction_report(
            preference_constraints,
            constraint_satisfied,
            constraint_unmet,
            constraint_warnings,
        ),
        "decision_log": [
            _decision(
                "validation_gate",
                "Validation passed" if not errors else f"Validation found {len(errors)} issues",
                "; ".join(errors[:3]) if errors else "All deterministic checks passed",
            )
        ],
    }


def check_validation(state: ItineraryState) -> str:
    if not state.get("validation_errors"):
        return "pass"
    if int(state.get("validation_rebuild_count") or 0) < 2:
        return "rebuild"
    return "pass"


graph = StateGraph(ItineraryState)

graph.add_node("cluster_by_neighborhood", cluster_by_neighborhood)
graph.add_node("build_itinerary", build_itinerary)
graph.add_node("align_flight_times", align_flight_times)
graph.add_node("plan_routes", plan_routes)
graph.add_node("validation_gate", validation_gate)

graph.set_entry_point("cluster_by_neighborhood")
graph.add_edge("cluster_by_neighborhood", "build_itinerary")
graph.add_edge("build_itinerary", "align_flight_times")
graph.add_edge("align_flight_times", "plan_routes")
graph.add_conditional_edges(
    "plan_routes",
    check_feasibility,
    {"swap": "plan_routes", "pass": "validation_gate"},
)
graph.add_conditional_edges(
    "validation_gate",
    check_validation,
    {"rebuild": "build_itinerary", "pass": END},
)

itinerary_graph = graph.compile()


def build_itinerary_subgraph():
    """Return the compiled itinerary-only StateGraph."""
    return itinerary_graph


async def run_itinerary_subgraph(trip_state: dict) -> dict:
    """
    Maps TripState fields into ItineraryState, invokes the subgraph, returns final ItineraryState.
    Called by the orchestrator as a regular async function.
    """
    itinerary_input: ItineraryState = {
        "trip_id": trip_state["trip_id"],
        "destination": trip_state["selected_destination"],
        "destination_coords": trip_state["selected_destination_coords"] or {"lat": 0.0, "lng": 0.0},
        "start_date": trip_state["start_date"],
        "end_date": trip_state["end_date"],
        "trip_duration_days": trip_state["trip_duration_days"],
        "members": trip_state["members"],
        "group_notes": trip_state.get("group_notes", ""),
        "preference_constraints": trip_state.get("preference_constraints", {}),
        "constraint_satisfaction": trip_state.get("constraint_satisfaction", {}),
        "activities": trip_state["activities"],
        "hotel": trip_state["hotel"],
        "flights": trip_state["flights"],
        "weather": trip_state.get("weather"),
        "clustered_activities": [],
        "days": [],
        "feasibility_swap_count": 0,
        "validation_rebuild_count": 0,
        "validation_errors": [],
        "decision_log": [],
        "error": None,
    }
    return await itinerary_graph.ainvoke(itinerary_input)


if __name__ == "__main__":
    import asyncio

    mock_activities = [
        {
            "place_id": "p1",
            "name": "City Park",
            "category": "outdoor",
            "address": "French Quarter, New Orleans, LA",
            "lat": 29.960,
            "lng": -90.060,
            "price_level": 0,
            "rating": 4.5,
            "tags": ["park", "outdoor"],
        },
        {
            "place_id": "p2",
            "name": "Jazz Museum",
            "category": "urban",
            "address": "French Quarter, New Orleans, LA",
            "lat": 29.961,
            "lng": -90.061,
            "price_level": 1,
            "rating": 4.7,
            "tags": ["museum", "historic"],
        },
        {
            "place_id": "p3",
            "name": "Cafe Du Monde",
            "category": "food",
            "address": "French Quarter, New Orleans, LA",
            "lat": 29.958,
            "lng": -90.062,
            "price_level": 1,
            "rating": 4.6,
            "tags": ["restaurant", "cafe"],
        },
        {
            "place_id": "p4",
            "name": "Audubon Park",
            "category": "outdoor",
            "address": "Garden District, New Orleans, LA",
            "lat": 29.924,
            "lng": -90.131,
            "price_level": 0,
            "rating": 4.4,
            "tags": ["park", "nature"],
        },
        {
            "place_id": "p5",
            "name": "Garden District Walk",
            "category": "urban",
            "address": "Garden District, New Orleans, LA",
            "lat": 29.926,
            "lng": -90.130,
            "price_level": 0,
            "rating": 4.3,
            "tags": ["historic", "walking"],
        },
    ]

    mock_state = {
        "trip_id": "test-001",
        "destination": "New Orleans, LA",
        "destination_coords": {"lat": 29.951, "lng": -90.071},
        "start_date": "2026-06-01",
        "end_date": "2026-06-03",
        "trip_duration_days": 2,
        "members": [
            {
                "member_id": "alice",
                "name": "Alice",
                "origin_city": "ORD",
                "budget_usd": 1200.0,
                "food_restrictions": ["vegetarian"],
                "preference_vector": {
                    "outdoor": 0.8,
                    "food": 0.7,
                    "nightlife": 0.2,
                    "urban": 0.6,
                    "shopping": 0.1,
                },
                "is_leader": True,
            },
            {
                "member_id": "bob",
                "name": "Bob",
                "origin_city": "ATL",
                "budget_usd": 1000.0,
                "food_restrictions": [],
                "preference_vector": {
                    "outdoor": 0.6,
                    "food": 0.8,
                    "nightlife": 0.5,
                    "urban": 0.4,
                    "shopping": 0.3,
                },
                "is_leader": False,
            },
        ],
        "activities": mock_activities,
        "hotel": {
            "name": "Hotel Monteleone",
            "address": "214 Royal St, New Orleans",
            "price_per_night_usd": 180.0,
            "total_price_usd": 360.0,
            "rating": 4.5,
            "is_estimated": False,
        },
        "flights": [
            {
                "member_id": "alice",
                "origin": "ORD",
                "destination": "MSY",
                "price_usd": 280.0,
                "airline": "Southwest",
                "depart_time": "2026-06-01T10:00:00",
                "return_time": "2026-06-03T17:00:00",
                "is_estimated": False,
            },
            {
                "member_id": "bob",
                "origin": "ATL",
                "destination": "MSY",
                "price_usd": 210.0,
                "airline": "Delta",
                "depart_time": "2026-06-01T11:30:00",
                "return_time": "2026-06-03T18:00:00",
                "is_estimated": False,
            },
        ],
        "weather": {
            "destination": "New Orleans",
            "date_range": "2026-06-01 to 2026-06-03",
            "avg_temp_c": 28.0,
            "precipitation_mm": 5.0,
            "summary": "Warm (28C avg), mostly dry",
        },
        "clustered_activities": [],
        "days": [],
        "feasibility_swap_count": 0,
        "validation_rebuild_count": 0,
        "validation_errors": [],
        "decision_log": [],
        "error": None,
    }

    async def test() -> None:
        result = await itinerary_graph.ainvoke(mock_state)
        print("\n=== ITINERARY SUBGRAPH RESULT ===")
        print(f"Days built: {len(result['days'])}")
        print(f"Validation errors: {result['validation_errors']}")
        print(f"Decision log entries: {len(result['decision_log'])}")
        for day in result["days"]:
            print(f"\nDay {day['day_number']} - {day['neighborhood']}")
            print(f"  Activities: {[activity.get('name') for activity in day['activities']]}")
            print(f"  Meals: {day['meals']}")
            print(f"  Estimated cost: ${day['estimated_day_cost_usd']}")

    asyncio.run(test())
