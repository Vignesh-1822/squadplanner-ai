"""Final trip pitch assembly node."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from agent.state import DecisionLogEntry, TripState
from config import get_llm, settings


def _message_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "".join(str(part.get("text", part)) if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def _destination_details(state: TripState) -> tuple[str, str]:
    selected = state.get("selected_destination") or ""
    for destination in state.get("candidate_destinations", []):
        if destination.get("id") == selected or destination.get("name") == selected:
            return destination.get("name", selected), destination.get("state", "")
    return selected, ""


def _days_summary(state: TripState) -> list[dict]:
    return [
        {
            "day_number": day.get("day_number"),
            "neighborhood": day.get("neighborhood"),
            "activities": [activity.get("name") for activity in day.get("activities", [])],
            "meals": day.get("meals", []),
            "schedule": day.get("schedule", []),
            "rationale": day.get("rationale", ""),
            "constraint_notes": day.get("constraint_notes", []),
        }
        for day in state.get("days", [])
    ]


def _readable_days_summary(days: list[dict]) -> str:
    lines = []
    for day in days:
        activities = ", ".join(day.get("activities", [])) or "No activities planned"
        meals = ", ".join(day.get("meals", [])) or "No meals planned"
        schedule = ", ".join(
            f"{entry.get('time')} {entry.get('label')}"
            for entry in day.get("schedule", [])
            if entry.get("time") and entry.get("label")
        )
        lines.append(
            f"Day {day.get('day_number')}: {day.get('neighborhood', 'Neighborhood TBD')}\n"
            f"  Activities: {activities}\n"
            f"  Meals: {meals}\n"
            f"  Schedule: {schedule or 'Schedule metadata unavailable'}\n"
            f"  Rationale: {day.get('rationale') or 'Unavailable'}\n"
            f"  Constraint notes: {', '.join(day.get('constraint_notes', [])) or 'None'}"
        )
    return "\n".join(lines)


async def assemble_output(state: TripState) -> dict:
    destination_name, destination_state = _destination_details(state)
    hotel = state.get("hotel") or {}
    weather = state.get("weather") or {}
    days = _days_summary(state)
    day_plan_summary = _readable_days_summary(days)
    preference_constraints = state.get("preference_constraints", {})
    constraint_satisfaction = state.get("constraint_satisfaction", {})

    if days:
        prompt = (
            "Generate a trip pitch written to sell this trip to the group.\n"
            "Write exactly 4 paragraphs. Do not shorten this. Minimum 80 words per paragraph.\n"
            "Paragraph 1: destination overview and why it fits this group.\n"
            "Paragraph 2: highlights from the itinerary, naming specific days and activities.\n"
            "Paragraph 3: logistics including hotel, weather, and what to expect.\n"
            "Paragraph 4: closing hype.\n\n"
            f"Destination: {destination_name}, {destination_state}\n"
            f"Trip dates: {state['start_date']} to {state['end_date']} "
            f"({state.get('trip_duration_days')} days)\n"
            f"Hotel: {hotel.get('name')}, ${float(hotel.get('price_per_night_usd', 0.0)):.0f} "
            f"per night, ${float(hotel.get('total_price_usd', 0.0)):.0f} total\n"
            f"Weather summary: {weather.get('summary', 'Not available')}\n"
            f"Day plan summary:\n{day_plan_summary}\n"
            f"Group size: {len(state['members'])}\n"
            f"Preference conflicts: {json.dumps(state.get('preference_conflicts', []))}\n"
            f"Natural-language preference constraints: {json.dumps(preference_constraints)}\n"
            f"Constraint satisfaction: {json.dumps(constraint_satisfaction)}"
        )
    else:
        prompt = (
            "Generate a shorter trip pitch based on destination and hotel only. "
            "Write 2-3 concise paragraphs that sell the trip to the group.\n\n"
            f"Destination: {destination_name}, {destination_state}\n"
            f"Trip dates: {state['start_date']} to {state['end_date']} "
            f"({state.get('trip_duration_days')} days)\n"
            f"Hotel: {hotel.get('name')}, ${float(hotel.get('price_per_night_usd', 0.0)):.0f} "
            f"per night, ${float(hotel.get('total_price_usd', 0.0)):.0f} total\n"
            f"Weather summary: {weather.get('summary', 'Not available')}\n"
            f"Group size: {len(state['members'])}\n"
            f"Preference conflicts: {json.dumps(state.get('preference_conflicts', []))}\n"
            f"Natural-language preference constraints: {json.dumps(preference_constraints)}\n"
            f"Constraint satisfaction: {json.dumps(constraint_satisfaction)}"
        )

    response = await get_llm().ainvoke(prompt)
    return {
        "trip_pitch": _message_text(response).strip(),
        "decision_log": [
            DecisionLogEntry(
                node="assemble_output",
                decision="Trip pitch generated",
                reason=f"{len(state.get('days', []))} days, {len(state['members'])} members",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        ],
    }


if __name__ == "__main__":
    class _FakeLLM:
        async def ainvoke(self, prompt: str) -> str:
            return (
                "New Orleans gives this group a trip with flavor, music, history, and enough walkable texture "
                "to make every day feel full.\n\n"
                "The itinerary balances the French Quarter, Garden District, live music, food stops, and local "
                "urban exploring without turning the trip into a checklist.\n\n"
                "Hotel Monteleone keeps the group close to the action, while warm and mostly dry weather makes "
                "the outdoor wandering realistic.\n\n"
                "This is the kind of long weekend that should feel easy to say yes to: memorable meals, late "
                "nights if people want them, and plenty to talk about afterward."
            )

    def _fake_get_llm() -> _FakeLLM:
        return _FakeLLM()

    get_llm = _fake_get_llm
    mock_state: TripState = {
        "trip_id": "mock",
        "members": [
            {
                "member_id": "alice",
                "name": "Alice",
                "origin_city": "CHI",
                "budget_usd": 1200.0,
                "food_restrictions": [],
                "preference_vector": {
                    "outdoor": 0.4,
                    "food": 0.9,
                    "nightlife": 0.7,
                    "urban": 0.8,
                    "shopping": 0.2,
                },
                "is_leader": True,
            },
            {
                "member_id": "bob",
                "name": "Bob",
                "origin_city": "ATL",
                "budget_usd": 950.0,
                "food_restrictions": ["shellfish"],
                "preference_vector": {
                    "outdoor": 0.3,
                    "food": 0.8,
                    "nightlife": 0.4,
                    "urban": 0.9,
                    "shopping": 0.3,
                },
                "is_leader": False,
            },
            {
                "member_id": "carla",
                "name": "Carla",
                "origin_city": "DEN",
                "budget_usd": 1100.0,
                "food_restrictions": [],
                "preference_vector": {
                    "outdoor": 0.6,
                    "food": 0.7,
                    "nightlife": 0.9,
                    "urban": 0.5,
                    "shopping": 0.4,
                },
                "is_leader": False,
            },
        ],
        "start_date": "2026-06-01",
        "end_date": "2026-06-04",
        "trip_duration_days": 3,
        "selected_destination": "New Orleans",
        "candidate_destinations": [{"name": "New Orleans", "state": "LA"}],
        "hotel": {
            "name": "Hotel Monteleone",
            "price_per_night_usd": 180,
            "total_price_usd": 540,
            "rating": 4.5,
            "is_estimated": False,
        },
        "weather": {"summary": "Warm (28°C avg), mostly dry"},
        "days": [
            {
                "day_number": 1,
                "date": "2026-06-01",
                "neighborhood": "French Quarter",
                "activities": [
                    {"name": "Jackson Square"},
                    {"name": "French Market"},
                    {"name": "Preservation Hall"},
                ],
                "meals": ["Cafe du Monde", "Napoleon House", "GW Fins"],
                "routes": [],
                "estimated_day_cost_usd": 120.0,
            },
            {
                "day_number": 2,
                "date": "2026-06-02",
                "neighborhood": "Garden District and Magazine Street",
                "activities": [
                    {"name": "Lafayette Cemetery No. 1"},
                    {"name": "Garden District walking tour"},
                    {"name": "Magazine Street shops"},
                ],
                "meals": ["Surrey's Cafe", "Commander's Palace", "Cochon"],
                "routes": [],
                "estimated_day_cost_usd": 150.0,
            },
            {
                "day_number": 3,
                "date": "2026-06-03",
                "neighborhood": "Bywater and Marigny",
                "activities": [
                    {"name": "Crescent Park"},
                    {"name": "Studio BE"},
                    {"name": "Frenchmen Street live music"},
                ],
                "meals": ["Elizabeth's", "Bacchanal", "Dat Dog"],
                "routes": [],
                "estimated_day_cost_usd": 130.0,
            },
        ],
        "preference_conflicts": [
            "nightlife conflict: Bob=0.4, Carla=0.9",
            "outdoor conflict: Alice=0.4, Carla=0.6",
        ],
    }  # type: ignore[typeddict-item]

    print(asyncio.run(assemble_output(mock_state)))
