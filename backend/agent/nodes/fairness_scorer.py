"""Fairness and compatibility scoring node."""

import asyncio
from collections import Counter
from datetime import datetime, timezone

from agent.state import DecisionLogEntry, FlightResult, TripState
from config import get_llm, settings


TAG_KEYWORDS = {
    "outdoor": ["park", "hiking", "nature", "trail"],
    "food": ["restaurant", "food", "cafe", "bakery"],
    "nightlife": ["bar", "night_club", "nightlife"],
    "urban": ["tourist_attraction", "museum", "art_gallery", "historic", "point_of_interest"],
    "shopping": ["shopping_mall", "store", "market"],
}


def _cheapest_member_flight(member_id: str, flights: list[FlightResult]) -> float:
    prices = [float(flight["price_usd"]) for flight in flights if flight.get("member_id") == member_id]
    return min(prices) if prices else 300.0


def _itinerary_tags(state: TripState) -> list[str]:
    return [
        tag
        for day in state.get("days", [])
        for activity in day.get("activities", [])
        for tag in activity.get("tags", [])
    ]


async def compute_fairness(state: TripState) -> dict:
    members = state["members"]
    hotel_per_person = float(state["hotel"]["total_price_usd"]) / len(members)

    fairness_scores: dict[str, float] = {}
    utilizations: list[float] = []
    for member in members:
        flight_cost = _cheapest_member_flight(member["member_id"], state.get("flights", []))
        member_cost = flight_cost + hotel_per_person
        utilization = member_cost / float(member["budget_usd"])
        utilizations.append(utilization)
        fairness_scores[member["member_id"]] = round(utilization, 3)

    spread = max(utilizations) - min(utilizations) if utilizations else 0.0
    fairness_passed = spread <= 0.3

    compatibility_scores: dict[str, float] = {}
    if not state.get("days"):
        compatibility_scores = {member["member_id"]: 0.5 for member in members}
    else:
        all_tags = _itinerary_tags(state)
        tag_counts = Counter(all_tags)
        total_tags = max(len(all_tags), 1)
        for member in members:
            preference_vector = member.get("preference_vector", {})
            score_total = 0.0
            for dimension, keywords in TAG_KEYWORDS.items():
                matching_count = sum(tag_counts.get(keyword, 0) for keyword in keywords)
                score_total += float(preference_vector.get(dimension, 0.0)) * (
                    matching_count / total_tags
                )
            compatibility_scores[member["member_id"]] = round(score_total / 5, 3)

    return {
        "fairness_scores": fairness_scores,
        "compatibility_scores": compatibility_scores,
        "fairness_passed": fairness_passed,
        "decision_log": [
            DecisionLogEntry(
                node="compute_fairness",
                decision="Fairness " + ("passed" if fairness_passed else "failed"),
                reason=f"Utilization spread: {spread:.2f}, threshold 0.30",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        ],
    }


if __name__ == "__main__":
    mock_state: TripState = {
        "trip_id": "mock",
        "members": [
            {
                "member_id": "alice",
                "name": "Alice",
                "origin_city": "CHI",
                "budget_usd": 1000.0,
                "food_restrictions": [],
                "preference_vector": {"food": 0.8, "outdoor": 0.5},
                "is_leader": True,
            }
        ],
        "start_date": "2026-06-01",
        "end_date": "2026-06-04",
        "flights": [{"member_id": "alice", "price_usd": 250.0}],
        "hotel": {"total_price_usd": 300.0},
        "days": [],
    }  # type: ignore[typeddict-item]

    print(asyncio.run(compute_fairness(mock_state)))
