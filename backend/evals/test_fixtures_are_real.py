"""Committed fixture-integrity checks."""

import json
from pathlib import Path
from datetime import date

import pytest

from evals.replay.tools import ReplayRecordingError, validate_recorded_tool_response
from evals.cases import load_cases

_TOOLS = Path(__file__).resolve().parent / "fixtures" / "tools"


def test_tool_fixtures_do_not_hide_degradation():
    for path in _TOOLS.glob("*/*.json"):
        envelope = json.loads(path.read_text(encoding="utf-8"))
        operation = envelope["operation"]
        response = envelope["response"]
        # K-002 is the sole, documented exception: flight fallback is the
        # current production baseline and must remain visibly estimated.
        validate_recorded_tool_response(operation, response, envelope.get("request"))
        if operation == "search_flights":
            assert response.get("is_estimated") is True


def test_case_tier_counts_and_labels():
    root = Path(__file__).resolve().parent / "cases"
    offline = list((root / "offline").glob("*.json"))
    live = list((root / "live").glob("*.json"))
    assert len(offline) == 30
    assert len(live) == 5
    for tier, paths in (("offline", offline), ("live", live)):
        for path in paths:
            assert json.loads(path.read_text(encoding="utf-8"))["tier"] == tier


def test_offline_manifest_covers_required_boundaries():
    cases = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (_TOOLS.parents[1] / "cases" / "offline").glob("*.json")
    ]
    assert any(len(case["payload"]["members"]) == 1 for case in cases)
    assert any(len(case["payload"]["members"]) == 8 for case in cases)
    assert any(case.get("graph_only") and "fourteen-day" in case["id"] for case in cases)
    restrictions = {
        restriction
        for case in cases
        for member in case["payload"]["members"]
        for restriction in member.get("food_restrictions", [])
    }
    assert {"vegetarian", "vegan", "halal", "gluten_free"} <= restrictions
    assert any("availability" in case.get("tags", []) for case in cases)


def test_live_cases_resolve_to_future_dates():
    assert all(
        date.fromisoformat(case["payload"]["start_date"]) > date.today()
        for case in load_cases("live")
    )


@pytest.mark.parametrize(
    ("operation", "response"),
    [
        ("search_hotels", {"is_estimated": True}),
        ("fetch_activities_by_category", []),
        ("get_route", {"distance_meters": 0, "duration_seconds": 0}),
        ("fetch_weather", {"summary": "Weather data unavailable"}),
    ],
)
def test_recorder_rejects_unlabelled_fallbacks(operation, response):
    with pytest.raises(ReplayRecordingError):
        validate_recorded_tool_response(operation, response)


def test_estimated_flight_exception_is_limited_to_k002_city_names():
    with pytest.raises(ReplayRecordingError):
        validate_recorded_tool_response(
            "search_flights",
            {"is_estimated": True},
            {"destination": "JFK"},
        )
    validate_recorded_tool_response(
        "search_flights",
        {"is_estimated": True},
        {"destination": "New York City"},
    )
