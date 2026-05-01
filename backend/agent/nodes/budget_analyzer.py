"""Budget analysis node."""

import asyncio
from datetime import datetime, timezone

from agent.state import DecisionLogEntry, FlightResult, TripState
from config import get_llm, settings


def _cheapest_flight_total(flights: list[FlightResult]) -> float:
    cheapest_by_member: dict[str, float] = {}
    for flight in flights:
        member_id = flight.get("member_id", "")
        if not member_id:
            continue
        price = float(flight.get("price_usd", 0.0))
        cheapest_by_member[member_id] = min(price, cheapest_by_member.get(member_id, price))
    return sum(cheapest_by_member.values())


async def budget_analysis(state: TripState) -> dict:
    flight_total = _cheapest_flight_total(state.get("flights", []))
    hotel = state.get("hotel")
    hotel_total = float(hotel["total_price_usd"]) if hotel else 0.0
    activity_estimate = 50.0 * len(state["members"]) * state["trip_duration_days"]
    total_estimated_cost = flight_total + hotel_total + activity_estimate
    group_budget = sum(float(member["budget_usd"]) for member in state["members"])

    budget_ceiling_hotel_usd = None
    if total_estimated_cost > 1.2 * group_budget:
        budget_status = "severe"
    elif total_estimated_cost > group_budget:
        budget_status = "moderate"
        budget_ceiling_hotel_usd = (
            float(hotel["total_price_usd"]) * 0.8 if hotel else group_budget * 0.25
        )
    else:
        budget_status = "ok"

    return {
        "budget_status": budget_status,
        "budget_ceiling_hotel_usd": budget_ceiling_hotel_usd,
        "decision_log": [
            DecisionLogEntry(
                node="budget_analysis",
                decision=f"Budget status: {budget_status}",
                reason=f"Total estimated: ${total_estimated_cost:.0f}, Group budget: ${group_budget:.0f}",
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
                "preference_vector": {},
                "is_leader": True,
            }
        ],
        "start_date": "2026-06-01",
        "end_date": "2026-06-04",
        "trip_duration_days": 3,
        "flights": [{"member_id": "alice", "price_usd": 250.0}],
        "hotel": {"total_price_usd": 300.0},
    }  # type: ignore[typeddict-item]

    print(asyncio.run(budget_analysis(mock_state)))
