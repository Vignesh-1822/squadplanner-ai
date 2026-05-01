"""Dynamic tool category selection node."""

import asyncio
from datetime import datetime, timezone

from agent.state import DecisionLogEntry, TripState
from config import get_llm, settings


CATEGORY_BY_DIMENSION = {
    "outdoor": "outdoor",
    "nightlife": "nightlife",
    "urban": "urban",
    "shopping": "shopping",
    "food": "food",
}


def _constraint_avoid_terms(preference_constraints: dict | None) -> set[str]:
    if not preference_constraints:
        return set()
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
    return terms


async def dynamic_tool_selection(state: TripState) -> dict:
    group_preferences = state["group_preference_vector"]
    preference_constraints = state.get("preference_constraints", {})
    avoid_terms = _constraint_avoid_terms(preference_constraints)
    included = ["food"]
    excluded: list[dict] = []
    avoids_nightlife = bool(avoid_terms.intersection({"nightlife", "night_club", "nightclub", "club", "clubs"}))

    for dimension in ("outdoor", "nightlife", "urban", "shopping"):
        score = float(group_preferences.get(dimension, 0.0))
        category = CATEGORY_BY_DIMENSION[dimension]
        if category in avoid_terms or dimension in avoid_terms or (category == "nightlife" and avoids_nightlife):
            excluded.append({category: "hard-avoided"})
        elif score >= 0.35:
            included.append(category)
        else:
            excluded.append({category: score})

    meal_requirements = preference_constraints.get("meal_requirements", {}).get("must_include", [])
    if meal_requirements and "food" not in included:
        included.append("food")

    included = list(dict.fromkeys(included))

    return {
        "active_tool_categories": included,
        "decision_log": [
            DecisionLogEntry(
                node="dynamic_tool_selection",
                decision=f"Selected {len(included)} tool categories",
                reason=f"Included: {included}. Excluded: {excluded}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        ],
    }


if __name__ == "__main__":
    mock_state: TripState = {
        "trip_id": "mock",
        "members": [],
        "start_date": "2026-06-01",
        "end_date": "2026-06-04",
        "group_preference_vector": {
            "outdoor": 0.7,
            "food": 0.1,
            "nightlife": 0.2,
            "urban": 0.4,
            "shopping": 0.1,
        },
    }  # type: ignore[typeddict-item]

    print(asyncio.run(dynamic_tool_selection(mock_state)))
