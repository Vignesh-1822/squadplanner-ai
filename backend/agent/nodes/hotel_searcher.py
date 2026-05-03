"""Hotel search node."""

import asyncio
from datetime import datetime, timezone

from agent.state import DecisionLogEntry, TripState
from config import get_llm, settings
from tools.serpapi import search_hotels


async def search_hotel(state: TripState) -> dict:
    group_budget = sum(float(member["budget_usd"]) for member in state["members"])
    ceiling = state.get("budget_ceiling_hotel_usd") or (group_budget * 0.3)
    hotel = await search_hotels(
        destination=state["selected_destination"],
        check_in=state["start_date"],
        check_out=state["end_date"],
        budget_ceiling_usd=ceiling,
        coords=state.get("selected_destination_coords"),
    )

    return {
        "hotel": hotel,
        "hotel_retry_count": state.get("hotel_retry_count", 0) + 1,
        "decision_log": [
            DecisionLogEntry(
                node="search_hotel",
                decision=f"Hotel selected: {hotel['name']}",
                reason=f"${hotel['total_price_usd']:.0f} total, ceiling was ${ceiling:.0f}",
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
        "selected_destination": "New York City, NY",
        "budget_ceiling_hotel_usd": 600.0,
        "hotel_retry_count": 0,
    }  # type: ignore[typeddict-item]

    print(asyncio.run(search_hotel(mock_state)))
