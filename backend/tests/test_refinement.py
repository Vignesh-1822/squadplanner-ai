"""Post-generation refinement parser and streaming tests."""

import json
from types import SimpleNamespace

import pytest

from agent.nodes.parse_refinement import (
    UnsupportedRefinement,
    build_refinement_state_patch,
    parse_refinement_message,
)
from utils import refinement_streaming


def _state() -> dict:
    return {
        "trip_id": "trip-1",
        "members": [{"member_id": "alice", "budget_usd": 1200.0}],
        "selected_destination": "Test City",
        "selected_destination_coords": {"lat": 1.0, "lng": 2.0},
        "start_date": "2026-07-10",
        "end_date": "2026-07-12",
        "trip_duration_days": 2,
        "flights": [{"member_id": "alice", "price_usd": 200.0}],
        "activities": [
            {
                "place_id": "museum-1",
                "name": "Modern Art Museum",
                "category": "urban",
                "address": "1 Main St",
                "lat": 1.0,
                "lng": 2.0,
                "price_level": 2,
                "rating": 4.7,
                "tags": ["museum"],
            }
        ],
        "active_tool_categories": ["urban", "food"],
        "hotel": {"name": "Hotel", "total_price_usd": 500.0, "price_per_night_usd": 250.0},
        "days": [
            {
                "day_number": 1,
                "date": "2026-07-10",
                "neighborhood": "Downtown",
                "activities": [{"name": "Modern Art Museum", "category": "urban"}],
                "meals": ["Breakfast", "Lunch", "Dinner"],
                "routes": [],
                "estimated_day_cost_usd": 180.0,
            },
            {
                "day_number": 2,
                "date": "2026-07-11",
                "neighborhood": "Central",
                "activities": [{"name": "Market", "category": "shopping"}],
                "meals": ["Breakfast", "Lunch", "Dinner"],
                "routes": [],
                "estimated_day_cost_usd": 220.0,
            },
        ],
        "weather": {"summary": "Mild"},
        "budget_status": "ok",
        "budget_ceiling_hotel_usd": None,
        "fairness_scores": {},
        "compatibility_scores": {},
        "fairness_passed": True,
        "trip_pitch": "Original pitch",
        "preference_constraints": {
            "activity_filters": {"avoid_tags": [], "prefer_tags": [], "required_tags": []},
            "meal_requirements": {"must_include": [], "avoid_terms": []},
            "schedule": {"pace": "balanced"},
            "hard_constraints": [],
            "soft_preferences": [],
        },
        "constraint_satisfaction": {},
        "decision_log": [],
        "refinement_history": [],
        "error": None,
    }


def _sse_payloads(frames: list[str]) -> list[dict]:
    payloads = []
    for frame in frames:
        if frame.startswith("data: "):
            payloads.append(json.loads(frame.removeprefix("data: ").strip()))
    return payloads


def test_parse_cheaper_day():
    parsed = parse_refinement_message("Make Day 2 cheaper")

    assert parsed["intent"] == "cheaper_day"
    assert parsed["day_number"] == 2
    assert parsed["rerun_from"] == "search_hotel"
    assert parsed["directives"]["cost_sensitivity"] == "lower_cost"


def test_parse_swap_museum_for_outdoors():
    parsed = parse_refinement_message("Swap the museum for something outdoors")

    assert parsed["intent"] == "swap_activity"
    assert parsed["directives"]["avoid_terms"] == ["museum"]
    assert parsed["directives"]["preferred_categories"] == ["outdoor"]
    assert parsed["requires_activity_category"] == "outdoor"


def test_parse_hotel_cheaper():
    parsed = parse_refinement_message("Make the hotel cheaper")
    patch, as_node = build_refinement_state_patch(_state(), parsed)

    assert parsed["intent"] == "cheaper_hotel"
    assert as_node == "budget_analysis"
    assert patch["budget_status"] == "moderate"
    assert patch["budget_ceiling_hotel_usd"] == 425.0


def test_parse_relaxed_pace_patch():
    parsed = parse_refinement_message("Keep the pace more relaxed")
    patch, as_node = build_refinement_state_patch(_state(), parsed)

    assert as_node == "search_hotel"
    assert patch["preference_constraints"]["schedule"]["pace"] == "relaxed"


def test_parse_rejects_destination_date_and_member_changes():
    for message in (
        "Change destination to Miami",
        "Move the dates to August",
        "Add another traveler",
    ):
        with pytest.raises(UnsupportedRefinement):
            parse_refinement_message(message)


class _FakeTrips:
    def __init__(self, doc: dict):
        self.doc = doc
        self.updates: list[dict] = []

    async def find_one(self, _query: dict, *_args):
        return self.doc

    async def update_one(self, _query: dict, update: dict, **_kwargs):
        self.updates.append(update)
        for key, value in update.get("$set", {}).items():
            target = self.doc
            parts = key.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value


class _FakeGraph:
    def __init__(self, state: dict):
        self.state = dict(state)
        self.next = ()
        self.as_node = None
        self.patch = None

    async def aget_state(self, _config):
        return SimpleNamespace(values=self.state, next=self.next)

    async def aupdate_state(self, _config, patch: dict, as_node: str):
        self.patch = patch
        self.as_node = as_node
        self.state.update(patch)
        self.next = ("run_itinerary_node",)

    async def astream_events(self, _graph_input, config, version):
        assert config["configurable"]["thread_id"] == "trip-1"
        assert version == "v2"
        yield {"event": "on_chain_start", "name": "run_itinerary_node"}
        self.state["trip_pitch"] = "Updated pitch"
        self.state["days"] = [
            {
                "day_number": 1,
                "date": "2026-07-10",
                "neighborhood": "Park",
                "activities": [{"name": "City Park", "category": "outdoor"}],
                "meals": ["Breakfast", "Lunch", "Dinner"],
                "routes": [],
                "estimated_day_cost_usd": 90.0,
            }
        ]
        self.next = ()


@pytest.mark.asyncio
async def test_stream_refinement_reenters_graph_and_completes(monkeypatch):
    state = _state()
    parsed = parse_refinement_message("Swap the museum for something outdoors")
    doc = {
        "trip_id": "trip-1",
        "status": "complete",
        "trip_pitch": "Original pitch",
        "final_state": state,
        "refinements": {
            "ref-1": {
                "refinement_id": "ref-1",
                "message": "Swap the museum for something outdoors",
                "parsed": parsed,
                "status": "queued",
            }
        },
    }
    trips = _FakeTrips(doc)
    graph = _FakeGraph(state)

    async def _fake_graph():
        return graph

    async def _fake_fetch(**_kwargs):
        return [
            {
                "place_id": "park-1",
                "name": "City Park",
                "category": "outdoor",
                "address": "2 Park Rd",
                "lat": 1.1,
                "lng": 2.1,
                "price_level": 0,
                "rating": 4.8,
                "tags": ["park", "outdoor"],
            }
        ]

    monkeypatch.setattr(refinement_streaming, "_get_orchestrator_graph", _fake_graph)
    monkeypatch.setattr(refinement_streaming, "get_collection", lambda _name: trips)
    monkeypatch.setattr(refinement_streaming, "fetch_activities_by_category", _fake_fetch)

    frames = [frame async for frame in refinement_streaming.stream_refinement_events("trip-1", "ref-1")]
    payloads = _sse_payloads(frames)
    event_types = [payload["event_type"] for payload in payloads]

    assert "REFINEMENT_PARSED" in event_types
    assert "NODE_PROGRESS" in event_types
    assert event_types[-1] == "REFINEMENT_COMPLETE"
    assert graph.as_node == "search_hotel"
    assert graph.patch["refinement_directives"]["preferred_categories"] == ["outdoor"]
    assert graph.patch["activities"][0]["name"] == "City Park"
    assert doc["refinements"]["ref-1"]["status"] == "complete"
    assert doc["itinerary"]["days"][0]["activities"][0]["name"] == "City Park"
