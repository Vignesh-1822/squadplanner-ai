"""Input parsing, validation, and preference aggregation node."""

import asyncio
from datetime import date, datetime, timezone
from itertools import combinations

from agent.state import DecisionLogEntry, MemberInput, TripState
from config import get_llm, settings


PREFERENCE_DIMENSIONS = ("outdoor", "food", "nightlife", "urban", "shopping")


def _parse_iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date string like YYYY-MM-DD.") from exc


def _member_label(member: MemberInput) -> str:
    return member.get("name") or member["member_id"]


def _normalize_preference_vector(vector: dict[str, float]) -> dict[str, float] | None:
    values = {dimension: max(float(vector.get(dimension, 0.0)), 0.0) for dimension in PREFERENCE_DIMENSIONS}
    total = sum(values.values())
    if total <= 0:
        return None
    return {dimension: value / total for dimension, value in values.items()}


def _destination_preference_vector(members: list[MemberInput]) -> dict[str, float]:
    normalized_vectors = [
        normalized
        for member in members
        if (normalized := _normalize_preference_vector(member.get("preference_vector", {}))) is not None
    ]
    if not normalized_vectors:
        return {dimension: 1.0 / len(PREFERENCE_DIMENSIONS) for dimension in PREFERENCE_DIMENSIONS}

    averaged = {
        dimension: sum(vector[dimension] for vector in normalized_vectors) / len(normalized_vectors)
        for dimension in PREFERENCE_DIMENSIONS
    }
    total = sum(averaged.values())
    if total <= 0:
        return {dimension: 1.0 / len(PREFERENCE_DIMENSIONS) for dimension in PREFERENCE_DIMENSIONS}
    return {dimension: value / total for dimension, value in averaged.items()}


async def parse_input(state: TripState) -> dict:
    members = state["members"]
    if not 1 <= len(members) <= 8:
        raise ValueError("Trip must include between 1 and 8 members.")

    leaders = [member for member in members if member.get("is_leader") is True]
    if len(leaders) != 1:
        raise ValueError("Exactly one trip member must have is_leader=True.")

    start_date = _parse_iso_date(state["start_date"], "start_date")
    end_date = _parse_iso_date(state["end_date"], "end_date")
    if start_date >= end_date:
        raise ValueError("start_date must be before end_date.")

    trip_duration_days = (end_date - start_date).days
    if not 2 <= trip_duration_days <= 14:
        raise ValueError("Trip duration must be between 2 and 14 days inclusive.")

    conflicts: list[str] = []
    for left, right in combinations(members, 2):
        left_prefs = left.get("preference_vector", {})
        right_prefs = right.get("preference_vector", {})
        for dimension in PREFERENCE_DIMENSIONS:
            left_value = float(left_prefs.get(dimension, 0.0))
            right_value = float(right_prefs.get(dimension, 0.0))
            if abs(left_value - right_value) > 0.5:
                conflicts.append(
                    f"{dimension} conflict: {_member_label(left)}={left_value:g}, "
                    f"{_member_label(right)}={right_value:g}"
                )

    group_preference_vector = {
        dimension: sum(float(member.get("preference_vector", {}).get(dimension, 0.0)) for member in members)
        / len(members)
        for dimension in PREFERENCE_DIMENSIONS
    }
    destination_preference_vector = _destination_preference_vector(members)

    return {
        "trip_duration_days": trip_duration_days,
        "preference_conflicts": conflicts,
        "group_preference_vector": group_preference_vector,
        "destination_preference_vector": destination_preference_vector,
        "decision_log": [
            DecisionLogEntry(
                node="parse_input",
                decision="Input validated",
                reason=(
                    f"{len(members)} members, {trip_duration_days} days, "
                    f"{len(conflicts)} conflicts detected"
                ),
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
                "budget_usd": 1200.0,
                "food_restrictions": [],
                "preference_vector": {
                    "outdoor": 0.8,
                    "food": 0.7,
                    "nightlife": 0.2,
                    "urban": 0.6,
                    "shopping": 0.1,
                },
                "is_leader": True,
            }
        ],
        "start_date": "2026-06-01",
        "end_date": "2026-06-04",
    }  # type: ignore[typeddict-item]

    print(asyncio.run(parse_input(mock_state)))
