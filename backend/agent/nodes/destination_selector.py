"""Destination selection node."""

import asyncio
import json
import math
import pathlib
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage

from agent.state import DecisionLogEntry, TripState
from config import get_llm, settings


PREFERENCE_DIMENSIONS = ("outdoor", "food", "nightlife", "urban", "shopping")
DESTINATIONS_PATH = pathlib.Path(__file__).parent.parent.parent / "data" / "destinations.json"
COST_INDEX = {"low": 1.0, "medium": 0.7, "high": 0.4}
ICONIC_INTENT_STYLES = {"big_city", "skyscrapers", "skyline", "national_park", "beach", "theme_parks"}


def _load_destinations() -> list[dict]:
    """Load the custom destination dataset fresh so JSON edits affect new trips."""
    return json.loads(DESTINATIONS_PATH.read_text(encoding="utf-8"))


def _previously_tried_destination_ids(state: TripState) -> set[str]:
    tried: set[str] = set()
    for entry in state.get("decision_log", []):
        decision = entry.get("decision", "")
        if "destination selected" not in decision.lower():
            continue
        reason = entry.get("reason", "")
        for destination in _load_destinations():
            destination_id = destination.get("id")
            if destination_id and (
                destination_id in decision
                or destination_id in reason
                or destination.get("name", "") in decision
                or destination.get("name", "") in reason
            ):
                tried.add(destination_id)
    return tried


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


def _adjusted_preference_vector(group_preference_vector: dict[str, float], preference_constraints: dict | None) -> dict:
    adjusted = dict(group_preference_vector)
    avoid_terms = _constraint_avoid_terms(preference_constraints)
    if avoid_terms.intersection({"nightlife", "night_club", "nightclub", "club", "clubs"}):
        adjusted["nightlife"] = 0.0
    return adjusted


def _vibe_score(vibe_tags: dict, key: str) -> float:
    return float(vibe_tags.get(key, 0.0))


def _normalize_destination_preference_vector(vector: dict[str, float]) -> dict[str, float]:
    values = {dimension: max(float(vector.get(dimension, 0.0)), 0.0) for dimension in PREFERENCE_DIMENSIONS}
    total = sum(values.values())
    if total <= 0:
        return {dimension: 1.0 / len(PREFERENCE_DIMENSIONS) for dimension in PREFERENCE_DIMENSIONS}
    return {dimension: value / total for dimension, value in values.items()}


def _cosine_similarity(destination_vector: dict, preference_vector: dict) -> float:
    destination_values = [_vibe_score(destination_vector, key) for key in PREFERENCE_DIMENSIONS]
    preference_values = [float(preference_vector.get(key, 0.0)) for key in PREFERENCE_DIMENSIONS]
    dot = sum(left * right for left, right in zip(destination_values, preference_values, strict=True))
    destination_norm = math.sqrt(sum(value * value for value in destination_values))
    preference_norm = math.sqrt(sum(value * value for value in preference_values))
    if destination_norm <= 0 or preference_norm <= 0:
        return 0.0
    return dot / (destination_norm * preference_norm)


def _average_member_budget(state: TripState) -> float:
    members = state.get("members", [])
    if not members:
        return 0.0
    return sum(float(member.get("budget_usd", 0.0)) for member in members) / len(members)


def _cost_weight_for_budget(avg_member_budget: float) -> float:
    if avg_member_budget <= 0:
        return 0.12
    if avg_member_budget < 700:
        return 0.25
    if avg_member_budget < 1200:
        return 0.18
    return 0.08


def _destination_intent(preference_constraints: dict | None) -> dict:
    if not preference_constraints:
        return {"styles": [], "landmarks": [], "preferred_types": [], "iconic_preference": False}
    intent = preference_constraints.get("destination_intent", {})
    if not isinstance(intent, dict):
        return {"styles": [], "landmarks": [], "preferred_types": [], "iconic_preference": False}
    return {
        "styles": [str(value).lower() for value in intent.get("styles", []) if str(value).strip()],
        "landmarks": [str(value).lower() for value in intent.get("landmarks", []) if str(value).strip()],
        "preferred_types": [str(value).lower() for value in intent.get("preferred_types", []) if str(value).strip()],
        "iconic_preference": bool(intent.get("iconic_preference", False)),
    }


def _has_iconic_intent(intent: dict) -> bool:
    return bool(intent.get("iconic_preference")) or bool(set(intent.get("styles", [])).intersection(ICONIC_INTENT_STYLES))


def _destination_tags(destination: dict) -> set[str]:
    tags = {
        str(tag).lower().replace(" ", "_")
        for tag in destination.get("prominence_tags", [])
        if str(tag).strip()
    }
    tags.update(
        str(tag).lower().replace(" ", "_")
        for tag in destination.get("best_for", [])
        if str(tag).strip()
    )
    tags.add(str(destination.get("type", "")).lower())
    return tags


def _popularity_fit(destination: dict) -> float:
    tier = int(destination.get("popularity_tier", 1) or 1)
    tier_fit = max(0.0, min((tier - 1) / 4, 1.0))
    iconic_score = max(0.0, min(float(destination.get("iconic_score", tier_fit) or 0.0), 1.0))
    return (0.7 * tier_fit) + (0.3 * iconic_score)


def _intent_fit(destination: dict, intent: dict) -> float:
    styles = set(intent.get("styles", []))
    landmarks = set(intent.get("landmarks", []))
    preferred_types = set(intent.get("preferred_types", []))
    if not styles and not landmarks and not preferred_types:
        return 0.0

    tags = _destination_tags(destination)
    destination_type = str(destination.get("type", "")).lower()
    matches = 0.0
    possible = 0.0

    if styles:
        possible += 1.0
        matches += len(styles.intersection(tags)) / len(styles)
    if landmarks:
        possible += 0.6
        matches += 0.6 * (len(landmarks.intersection(tags)) / len(landmarks))
    if preferred_types:
        possible += 1.0
        matches += 1.0 if destination_type in preferred_types else 0.0

    return max(0.0, min(matches / possible if possible else 0.0, 1.0))


def _score_destination(
    destination: dict,
    group_preference_vector: dict[str, float],
    preference_constraints: dict | None = None,
    avg_member_budget: float = 0.0,
) -> float:
    adjusted_preferences = _adjusted_preference_vector(group_preference_vector, preference_constraints)
    adjusted_preferences = _normalize_destination_preference_vector(adjusted_preferences)
    intent = _destination_intent(preference_constraints)
    vibe_tags = destination.get("vibe_tags", {})
    shape_fit = _cosine_similarity(vibe_tags, adjusted_preferences)
    cost_fit = COST_INDEX.get(destination.get("cost_level", "medium"), 0.7)
    intent_fit = _intent_fit(destination, intent)
    popularity_fit = _popularity_fit(destination)
    cost_weight = _cost_weight_for_budget(avg_member_budget)
    intent_weight = 0.24 if intent_fit > 0 else 0.04
    popularity_weight = 0.18 if _has_iconic_intent(intent) else 0.08
    shape_weight = max(0.35, 1.0 - cost_weight - intent_weight - popularity_weight)
    score = (
        (shape_weight * shape_fit)
        + (cost_weight * cost_fit)
        + (intent_weight * intent_fit)
        + (popularity_weight * popularity_fit)
    )
    avoid_terms = _constraint_avoid_terms(preference_constraints)
    if avoid_terms.intersection({"nightlife", "night_club", "nightclub", "club", "clubs"}):
        score -= 0.15 * float(destination.get("vibe_tags", {}).get("nightlife", 0.0))
    return max(score, 0.0)


def _destination_key(destination: dict) -> tuple[str, str]:
    name = str(destination.get("name") or "").lower().strip()
    return str(destination.get("id", "")), name


def _add_candidate(
    selected: list[tuple[dict, float]],
    seen: set[tuple[str, str]],
    candidate: tuple[dict, float],
    limit: int,
) -> bool:
    if len(selected) >= limit:
        return False
    key = _destination_key(candidate[0])
    if key in seen or any(key[1] == existing_key[1] for existing_key in seen):
        return False
    selected.append(candidate)
    seen.add(key)
    return True


def _diverse_top_destinations(
    scored_destinations: list[tuple[dict, float]],
    limit: int = 5,
    allow_same_type: bool = False,
) -> list[tuple[dict, float]]:
    sorted_destinations = sorted(scored_destinations, key=lambda item: item[1], reverse=True)
    selected: list[tuple[dict, float]] = []
    type_counts: dict[str, int] = {}
    state_counts: dict[str, int] = {}
    seen: set[tuple[str, str]] = set()

    for destination, score in sorted_destinations:
        destination_type = str(destination.get("type") or "unknown")
        state = str(destination.get("state") or "unknown")
        key = _destination_key(destination)
        if key in seen or any(key[1] == existing_key[1] for existing_key in seen):
            continue
        if not allow_same_type and type_counts.get(destination_type, 0) >= 2:
            continue
        if state_counts.get(state, 0) >= 2:
            continue
        selected.append((destination, score))
        seen.add(key)
        type_counts[destination_type] = type_counts.get(destination_type, 0) + 1
        state_counts[state] = state_counts.get(state, 0) + 1
        if len(selected) == limit:
            return selected

    for destination, score in sorted_destinations:
        if any(destination.get("id") == chosen.get("id") for chosen, _ in selected):
            continue
        _add_candidate(selected, seen, (destination, score), limit)
        if len(selected) == limit:
            break
    return selected


def _budget_logistics_candidates(scored_destinations: list[tuple[dict, float]]) -> list[tuple[dict, float]]:
    return sorted(
        scored_destinations,
        key=lambda item: (
            COST_INDEX.get(item[0].get("cost_level", "medium"), 0.7),
            item[1],
            _popularity_fit(item[0]),
        ),
        reverse=True,
    )


def _wildcard_candidates(scored_destinations: list[tuple[dict, float]]) -> list[tuple[dict, float]]:
    return sorted(
        [
            item
            for item in scored_destinations
            if int(item[0].get("popularity_tier", 1) or 1) <= 3
        ],
        key=lambda item: item[1],
        reverse=True,
    )


def _popular_iconic_candidates(scored_destinations: list[tuple[dict, float]], intent: dict) -> list[tuple[dict, float]]:
    iconic_intent = _has_iconic_intent(intent)
    return sorted(
        [
            item
            for item in scored_destinations
            if int(item[0].get("popularity_tier", 1) or 1) >= 4
            and (not iconic_intent or _intent_fit(item[0], intent) > 0 or _popularity_fit(item[0]) >= 0.75)
        ],
        key=lambda item: (item[1], _intent_fit(item[0], intent), _popularity_fit(item[0])),
        reverse=True,
    )


def _slotted_top_destinations(
    scored_destinations: list[tuple[dict, float]],
    preference_constraints: dict | None,
    limit: int = 5,
) -> list[tuple[dict, float]]:
    intent = _destination_intent(preference_constraints)
    iconic_slots = 2 if _has_iconic_intent(intent) else 1
    allow_same_type = bool(set(intent.get("preferred_types", [])).intersection({"major_city", "national_park"}))
    selected: list[tuple[dict, float]] = []
    seen: set[tuple[str, str]] = set()

    pure_fit = _diverse_top_destinations(scored_destinations, limit=len(scored_destinations), allow_same_type=allow_same_type)
    for candidate in pure_fit:
        _add_candidate(selected, seen, candidate, 2)

    for candidate in _popular_iconic_candidates(scored_destinations, intent):
        if sum(int(item[0].get("popularity_tier", 1) or 1) >= 4 for item in selected) >= iconic_slots:
            break
        _add_candidate(selected, seen, candidate, limit)

    for candidate in _budget_logistics_candidates(scored_destinations):
        if _add_candidate(selected, seen, candidate, limit):
            break

    for candidate in _wildcard_candidates(scored_destinations):
        if _add_candidate(selected, seen, candidate, limit):
            break

    for candidate in pure_fit:
        _add_candidate(selected, seen, candidate, limit)
        if len(selected) >= limit:
            break

    return sorted(selected[:limit], key=lambda item: item[1], reverse=True)


async def select_destination(state: TripState) -> dict:
    raw_group_preference_vector = state["group_preference_vector"]
    group_preference_vector = state.get("destination_preference_vector") or _normalize_destination_preference_vector(
        raw_group_preference_vector
    )
    preference_constraints = state.get("preference_constraints", {})
    tried_ids = _previously_tried_destination_ids(state)
    destinations = _load_destinations()
    avg_member_budget = _average_member_budget(state)

    scored_destinations = [
        (
            destination,
            _score_destination(
                destination,
                group_preference_vector,
                preference_constraints,
                avg_member_budget,
            ),
        )
        for destination in destinations
        if destination.get("id") not in tried_ids
    ]
    top_destinations = _slotted_top_destinations(scored_destinations, preference_constraints, limit=5)

    llm_destinations = [
        {
            "id": destination.get("id"),
            "name": destination.get("name"),
            "state": destination.get("state"),
            "type": destination.get("type"),
            "cost_level": destination.get("cost_level"),
            "vibe_tags": destination.get("vibe_tags", {}),
            "popularity_tier": destination.get("popularity_tier", 1),
            "iconic_score": destination.get("iconic_score", 0.0),
            "prominence_tags": destination.get("prominence_tags", []),
            "score": round(score, 4),
        }
        for destination, score in top_destinations
    ]
    prompt = (
        "Given these top 5 destinations as a JSON list, the group's preference vector, "
        "trip dates, preference conflicts, and natural-language constraints, write a 1-2 sentence "
        "'why this fits your group' explanation for each destination. Take hard constraints seriously. "
        "Return ONLY a raw JSON array of exactly 5 strings, "
        "no markdown, no backticks, no explanation. Example format: "
        '[\"reason1\", \"reason2\", \"reason3\", \"reason4\", \"reason5\"]\n\n'
        f"destinations: {json.dumps(llm_destinations)}\n"
        f"group_preference_vector: {json.dumps(raw_group_preference_vector)}\n"
        f"destination_preference_vector: {json.dumps(group_preference_vector)}\n"
        f"start_date: {state['start_date']}\n"
        f"end_date: {state['end_date']}\n"
        f"group_notes: {json.dumps(state.get('group_notes', ''))}\n"
        f"preference_conflicts: {json.dumps(state.get('preference_conflicts', []))}\n"
        f"preference_constraints: {json.dumps(preference_constraints)}"
    )

    response = get_llm().invoke([HumanMessage(content=prompt)])
    text = response.content
    if isinstance(text, list):
        text = "".join(str(part.get("text", part)) if isinstance(part, dict) else str(part) for part in text)
    text = str(text).strip().strip("```json").strip("```").strip()
    try:
        parsed_reasons = json.loads(text)
        if not isinstance(parsed_reasons, list) or len(parsed_reasons) != len(top_destinations):
            raise ValueError("LLM response was not the expected JSON array length.")
    except (json.JSONDecodeError, ValueError):
        print(f"Destination selector LLM raw response: {response.content}")
        parsed_reasons = []

    reasons = [str(reason) for reason in parsed_reasons[: len(top_destinations)]]
    reasons.extend([""] * (len(top_destinations) - len(reasons)))

    candidate_destinations = []
    for index, (destination, score) in enumerate(top_destinations):
        candidate_destinations.append(
            {
                "id": str(destination.get("id", "")),
                "name": str(destination.get("name", "")),
                "state": str(destination.get("state", "")),
                "type": str(destination.get("type", "")),
                "score": round(score, 4),
                "coords": {
                    "lat": float(destination.get("lat", 0.0)),
                    "lng": float(destination.get("lng", 0.0)),
                },
                "llm_reasoning": reasons[index],
                "cost_level": str(destination.get("cost_level", "")),
                "nearest_airports": destination.get("nearest_airports", []),
            }
        )

    selected_name = candidate_destinations[0]["name"] if candidate_destinations else "none"
    selected_id = candidate_destinations[0]["id"] if candidate_destinations else "none"
    return {
        "candidate_destinations": candidate_destinations,
        "destination_retry_count": state.get("destination_retry_count", 0) + 1,
        "decision_log": [
            DecisionLogEntry(
                node="select_destination",
                decision=f"Destination selected candidates: {selected_id}",
                reason=f"Top candidate was {selected_name}; scored {len(candidate_destinations)} destinations",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        ],
    }


if __name__ == "__main__":
    class _FakeResponse:
        content = json.dumps(
            [
                "Strong outdoor and food balance for the group.",
                "Good mix of urban energy, meals, and relaxed pacing.",
                "Fits the group's budget while keeping activities varied.",
                "A practical option with enough variety for mixed preferences.",
                "Solid compromise across the highest-scoring interests.",
            ]
        )

    class _FakeLLM:
        def invoke(self, messages: list[HumanMessage]) -> _FakeResponse:
            return _FakeResponse()

    def _fake_get_llm() -> _FakeLLM:
        return _FakeLLM()

    get_llm = _fake_get_llm
    mock_state: TripState = {
        "trip_id": "mock",
        "members": [],
        "start_date": "2026-06-01",
        "end_date": "2026-06-04",
        "group_preference_vector": {
            "outdoor": 0.7,
            "food": 0.8,
            "nightlife": 0.2,
            "urban": 0.4,
            "shopping": 0.1,
        },
        "preference_conflicts": [],
        "decision_log": [],
        "destination_retry_count": 0,
    }  # type: ignore[typeddict-item]

    print(asyncio.run(select_destination(mock_state)))
