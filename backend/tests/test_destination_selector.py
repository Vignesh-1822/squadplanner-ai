"""Destination scoring regression tests."""

import json
import pytest
from pathlib import Path

from agent.nodes.input_parser import parse_input
from agent.nodes.destination_selector import (
    PREFERENCE_DIMENSIONS,
    _diverse_top_destinations,
    _load_destinations,
    _score_destination,
    _slotted_top_destinations,
)


def _case_payload(case_id: str) -> dict:
    cases = json.loads(Path("tests/demo_input_cases.json").read_text(encoding="utf-8"))["cases"]
    return next(case["payload"] for case in cases if case["id"] == case_id)


def _group_preferences(payload: dict) -> dict[str, float]:
    members = payload["members"]
    return {
        dimension: sum(float(member["preference_vector"].get(dimension, 0.0)) for member in members)
        / len(members)
        for dimension in PREFERENCE_DIMENSIONS
    }


def _avg_budget(payload: dict) -> float:
    return sum(float(member["budget_usd"]) for member in payload["members"]) / len(payload["members"])


def _empty_constraints() -> dict:
    return {
        "activity_filters": {"avoid_tags": [], "prefer_tags": [], "required_tags": []},
        "hard_constraints": [],
        "destination_intent": {
            "styles": [],
            "landmarks": [],
            "preferred_types": [],
            "iconic_preference": False,
        },
    }


def _intent_constraints(
    styles: list[str],
    preferred_types: list[str],
    landmarks: list[str] | None = None,
    iconic_preference: bool = True,
) -> dict:
    constraints = _empty_constraints()
    constraints["destination_intent"] = {
        "styles": styles,
        "landmarks": landmarks or [],
        "preferred_types": preferred_types,
        "iconic_preference": iconic_preference,
    }
    return constraints


async def _top_destinations(payload: dict, constraints: dict | None = None) -> list[tuple[dict, float]]:
    state = {
        "trip_id": "test-trip",
        **payload,
        "decision_log": [],
        "destination_retry_count": 0,
    }
    parsed = await parse_input(state)  # type: ignore[arg-type]
    prefs = parsed["destination_preference_vector"]
    avg_budget = _avg_budget(payload)
    constraints = constraints or _empty_constraints()
    scored = [
        (destination, _score_destination(destination, prefs, constraints, avg_budget))
        for destination in _load_destinations()
    ]
    return _slotted_top_destinations(scored, constraints)


def _top_names(payload: dict) -> list[str]:
    prefs = _group_preferences(payload)
    avg_budget = _avg_budget(payload)
    scored = [
        (destination, _score_destination(destination, prefs, {}, avg_budget))
        for destination in _load_destinations()
    ]
    return [destination["name"] for destination, _ in _diverse_top_destinations(scored)]


def test_destination_selector_uses_destinations_dataset():
    names = {destination["name"] for destination in _load_destinations()}

    assert "Badlands National Park" in names
    assert "Guadalupe Mountains National Park" in names
    assert "Matagorda" in names


def test_destinations_include_popularity_metadata():
    destinations = _load_destinations()

    assert all("popularity_tier" in destination for destination in destinations)
    assert all("iconic_score" in destination for destination in destinations)
    assert all(isinstance(destination.get("prominence_tags"), list) for destination in destinations)

    chicago = next(destination for destination in destinations if destination["name"] == "Chicago")
    assert chicago["popularity_tier"] == 5
    assert {"big_city", "skyscrapers", "skyline"}.issubset(set(chicago["prominence_tags"]))


def test_weight_conflict_case_no_longer_collapses_to_same_outdoor_options():
    top_names = _top_names(_case_payload("02_preference_weight_conflict"))
    old_repeated_options = {
        "Badlands National Park",
        "Guadalupe Mountains National Park",
        "Bisti/De-Na-Zin Wilderness",
        "Bonneville Salt Flats",
        "Matagorda",
    }

    assert top_names != list(old_repeated_options)
    assert len(set(top_names).intersection(old_repeated_options)) <= 1


@pytest.mark.asyncio
async def test_normalized_destination_vector_keeps_raw_group_vector_unchanged():
    payload = _case_payload("08_big_city_skyscraper_intent")
    parsed = await parse_input(
        {
            "trip_id": "test-trip",
            **payload,
            "decision_log": [],
            "destination_retry_count": 0,
        }  # type: ignore[arg-type]
    )

    raw_sum = sum(parsed["group_preference_vector"].values())
    destination_sum = sum(parsed["destination_preference_vector"].values())

    assert raw_sum > 1.0
    assert destination_sum == pytest.approx(1.0)
    assert parsed["group_preference_vector"] != parsed["destination_preference_vector"]


@pytest.mark.asyncio
async def test_urban_skyscraper_intent_includes_major_iconic_cities():
    top = await _top_destinations(
        _case_payload("08_big_city_skyscraper_intent"),
        _intent_constraints(
            styles=["big_city", "skyscrapers", "skyline", "museums", "nightlife_city"],
            landmarks=["skyscrapers", "skyline", "museums"],
            preferred_types=["major_city"],
        ),
    )
    names = {destination["name"] for destination, _ in top}
    major_city_count = sum(destination["type"] == "major_city" for destination, _ in top)
    iconic_names = {"New York City", "Chicago", "San Francisco", "Boston", "Los Angeles", "Seattle", "Miami"}

    assert major_city_count >= 2
    assert names.intersection(iconic_names)


@pytest.mark.asyncio
async def test_national_park_intent_includes_tier_5_national_park():
    payload = _case_payload("04_budget_limit_crossing")
    top = await _top_destinations(
        payload,
        _intent_constraints(styles=["national_park"], preferred_types=["national_park"]),
    )

    assert any(
        destination["type"] == "national_park" and destination["popularity_tier"] == 5
        for destination, _ in top
    )


@pytest.mark.asyncio
async def test_beach_intent_includes_popular_beach_or_island():
    payload = _case_payload("07_long_six_member_high_conflict_trip")
    top = await _top_destinations(
        payload,
        _intent_constraints(styles=["beach"], preferred_types=["beach_town", "island"]),
    )

    assert any(
        destination["popularity_tier"] >= 4
        and (
            destination["type"] in {"beach_town", "island"}
            or "beach" in destination.get("prominence_tags", [])
        )
        for destination, _ in top
    )


@pytest.mark.asyncio
async def test_tight_budget_case_still_prioritizes_low_cost_destinations():
    payload = _case_payload("04_budget_limit_crossing")
    top = await _top_destinations(payload)

    assert sum(destination["cost_level"] == "low" for destination, _ in top) >= 4


@pytest.mark.asyncio
async def test_balanced_trip_keeps_wildcard_or_niche_option():
    top = await _top_destinations(_case_payload("02_preference_weight_conflict"))

    assert any(destination["popularity_tier"] <= 3 for destination, _ in top)
