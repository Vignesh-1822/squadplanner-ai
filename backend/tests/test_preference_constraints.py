"""Natural-language preference constraint tests."""

import pytest
from fastapi.testclient import TestClient

from agent.graph import _filter_activities_by_constraints
from agent.nodes import preference_constraints as preference_node
from agent.nodes.preference_constraints import extract_preference_constraints
from agent.nodes.tool_selector import dynamic_tool_selection
from agent.subgraphs import itinerary as itinerary_module
from agent.subgraphs.itinerary import build_itinerary
from agent.subgraphs.itinerary import validation_gate
from api.trips import CreateTripRequest, _initial_trip_state
from main import app


class _MalformedLLM:
    async def ainvoke(self, _prompt: str):
        return "not-json"


class _RationaleLLM:
    def __init__(self):
        self.prompt = ""

    async def ainvoke(self, prompt: str):
        self.prompt = prompt
        return """
        [
          {
            "day_number": 1,
            "date": "2026-07-10",
            "neighborhood": "Downtown",
            "activities": ["Museum", "Park"],
            "meals": ["Hotel breakfast", "Cafe lunch", "Italian dinner"],
            "schedule": [{"time": "10:30", "type": "activity", "label": "Museum", "notes": "Late start"}],
            "estimated_day_cost_usd": 100,
            "rationale": "This day keeps the group downtown for museums, parks, and a relaxed late start.",
            "constraint_notes": ["No clubs scheduled.", "Includes Italian dinner.", "Starts after 10:00."]
          }
        ]
        """


def _constraints() -> dict:
    return {
        "raw_member_notes": [],
        "raw_group_notes": "",
        "hard_constraints": [
            {
                "source": "alice",
                "type": "avoid",
                "applies_to": "activities",
                "target": "nightlife",
                "terms": ["club", "nightclub", "night_club"],
                "text": "no clubs",
            }
        ],
        "soft_preferences": [],
        "schedule": {
            "avoid_early_mornings": True,
            "earliest_start_time": "10:00",
            "pace": "relaxed",
        },
        "activity_filters": {
            "avoid_tags": ["nightlife", "night_club", "club"],
            "prefer_tags": [],
            "required_tags": [],
        },
        "meal_requirements": {
            "must_include": [{"cuisine": "italian", "min_count": 1, "source": "alice"}],
            "avoid_terms": [],
        },
        "destination_intent": {
            "styles": [],
            "landmarks": [],
            "preferred_types": [],
            "iconic_preference": False,
        },
    }


@pytest.mark.asyncio
async def test_extract_preference_constraints_fallback(monkeypatch):
    monkeypatch.setattr(preference_node, "get_llm", lambda: _MalformedLLM())
    state = {
        "members": [
            {
                "member_id": "alice",
                "name": "Alice",
                "preference_notes": "Hates early mornings, no clubs, wants Italian food at least once.",
            }
        ],
        "group_notes": "Keep this relaxed and not packed.",
    }

    result = await extract_preference_constraints(state)  # type: ignore[arg-type]
    constraints = result["preference_constraints"]

    assert constraints["schedule"]["avoid_early_mornings"] is True
    assert constraints["schedule"]["earliest_start_time"] == "10:00"
    assert constraints["schedule"]["pace"] == "relaxed"
    assert "nightlife" in constraints["activity_filters"]["avoid_tags"]
    assert constraints["meal_requirements"]["must_include"][0]["cuisine"] == "italian"


@pytest.mark.asyncio
async def test_extract_destination_intent_fallback_for_big_city_skyscrapers(monkeypatch):
    monkeypatch.setattr(preference_node, "get_llm", lambda: _MalformedLLM())
    state = {
        "members": [
            {
                "member_id": "ava",
                "name": "Ava",
                "preference_notes": "I like big cities and urban exploration and want great nightclubs.",
            },
            {
                "member_id": "ben",
                "name": "Ben",
                "preference_notes": "Urban neighborhoods with dense skyscrapers and good food are the priority.",
            },
            {
                "member_id": "chloe",
                "name": "Chloe",
                "preference_notes": "Museums, architecture, and a city with tall skyscrapers.",
            },
        ],
        "group_notes": "People are flying from far apart. Keep the first day light.",
    }

    result = await extract_preference_constraints(state)  # type: ignore[arg-type]
    intent = result["preference_constraints"]["destination_intent"]

    assert {"big_city", "skyscrapers", "museums", "architecture"}.issubset(set(intent["styles"]))
    assert "major_city" in intent["preferred_types"]
    assert intent["iconic_preference"] is True


@pytest.mark.asyncio
async def test_dynamic_tool_selection_excludes_hard_avoided_nightlife():
    result = await dynamic_tool_selection(
        {
            "group_preference_vector": {
                "outdoor": 0.2,
                "food": 0.9,
                "nightlife": 0.9,
                "urban": 0.2,
                "shopping": 0.2,
            },
            "preference_constraints": _constraints(),
        }  # type: ignore[arg-type]
    )

    assert "food" in result["active_tool_categories"]
    assert "nightlife" not in result["active_tool_categories"]


def test_activity_filter_removes_avoided_clubs():
    activities = [
        {"name": "Downtown Nightclub", "category": "nightlife", "tags": ["night_club"]},
        {"name": "Modern Art Museum", "category": "urban", "tags": ["museum"]},
    ]

    filtered, removed = _filter_activities_by_constraints(activities, _constraints())  # type: ignore[arg-type]

    assert removed == 1
    assert [activity["name"] for activity in filtered] == ["Modern Art Museum"]


@pytest.mark.asyncio
async def test_itinerary_validation_catches_unmet_constraints():
    state = {
        "trip_duration_days": 1,
        "members": [{"member_id": "alice", "budget_usd": 2000, "food_restrictions": []}],
        "preference_constraints": _constraints(),
        "flights": [{"price_usd": 0}],
        "hotel": {"total_price_usd": 0},
        "days": [
            {
                "day_number": 1,
                "date": "2026-07-10",
                "neighborhood": "Downtown",
                "activities": [
                    {"name": "Night Club", "category": "nightlife", "tags": ["night_club"]},
                    {"name": "Museum", "category": "urban", "tags": ["museum"]},
                    {"name": "Park", "category": "outdoor", "tags": ["park"]},
                    {"name": "Market", "category": "shopping", "tags": ["market"]},
                ],
                "meals": ["Hotel breakfast", "Cafe lunch", "Bistro dinner"],
                "schedule": [{"time": "09:00", "type": "activity", "label": "Museum"}],
                "routes": [],
                "estimated_day_cost_usd": 0,
            }
        ],
    }

    result = await validation_gate(state)  # type: ignore[arg-type]

    assert result["validation_errors"]
    assert result["constraint_satisfaction"]["passed"] is False
    assert any("italian" in error.lower() for error in result["validation_errors"])
    assert any("avoided activity" in error.lower() for error in result["validation_errors"])
    assert any("09:00" in error for error in result["validation_errors"])


@pytest.mark.asyncio
async def test_itinerary_validation_passes_satisfied_constraints():
    state = {
        "trip_duration_days": 1,
        "members": [{"member_id": "alice", "budget_usd": 2000, "food_restrictions": []}],
        "preference_constraints": _constraints(),
        "flights": [{"price_usd": 0}],
        "hotel": {"total_price_usd": 0},
        "days": [
            {
                "day_number": 1,
                "date": "2026-07-10",
                "neighborhood": "Downtown",
                "activities": [
                    {"name": "Museum", "category": "urban", "tags": ["museum"]},
                    {"name": "Park", "category": "outdoor", "tags": ["park"]},
                ],
                "meals": ["Hotel breakfast", "Cafe lunch", "Italian dinner"],
                "schedule": [{"time": "10:30", "type": "activity", "label": "Museum"}],
                "routes": [],
                "estimated_day_cost_usd": 0,
            }
        ],
    }

    result = await validation_gate(state)  # type: ignore[arg-type]

    assert result["validation_errors"] == []
    assert result["constraint_satisfaction"]["passed"] is True


@pytest.mark.asyncio
async def test_build_itinerary_preserves_day_rationale_and_constraint_notes(monkeypatch):
    llm = _RationaleLLM()
    monkeypatch.setattr(itinerary_module, "get_llm", lambda: llm)

    result = await build_itinerary(
        {
            "trip_id": "trip-1",
            "destination": "Test City",
            "destination_coords": {"lat": 0.0, "lng": 0.0},
            "start_date": "2026-07-10",
            "end_date": "2026-07-11",
            "trip_duration_days": 1,
            "members": [
                {
                    "member_id": "alice",
                    "name": "Alice",
                    "origin_city": "ORD",
                    "budget_usd": 1500,
                    "food_restrictions": ["vegetarian"],
                    "preference_vector": {"outdoor": 0.6, "food": 0.8, "nightlife": 0.1, "urban": 0.7, "shopping": 0.2},
                    "preference_notes": "No clubs. Hates early mornings. Wants Italian food.",
                    "is_leader": True,
                }
            ],
            "group_notes": "Keep the trip relaxed.",
            "preference_constraints": _constraints(),
            "constraint_satisfaction": {},
            "activities": [
                {"name": "Museum", "category": "urban", "address": "Downtown", "lat": 0, "lng": 0, "tags": ["museum"]},
                {"name": "Park", "category": "outdoor", "address": "Downtown", "lat": 0, "lng": 0, "tags": ["park"]},
            ],
            "hotel": {"name": "Hotel", "address": "Downtown", "total_price_usd": 300},
            "flights": [],
            "weather": {"summary": "Mild"},
            "clustered_activities": [
                {
                    "day": 1,
                    "neighborhood": "Downtown",
                    "activities": [
                        {"name": "Museum", "category": "urban"},
                        {"name": "Park", "category": "outdoor"},
                    ],
                }
            ],
            "days": [],
            "feasibility_swap_count": 0,
            "validation_rebuild_count": 0,
            "validation_errors": [],
            "decision_log": [],
            "error": None,
        }  # type: ignore[arg-type]
    )

    assert "rationale: str" in llm.prompt
    assert "constraint_notes" in llm.prompt
    assert result["days"][0]["rationale"].startswith("This day keeps the group downtown")
    assert result["days"][0]["constraint_notes"] == [
        "No clubs scheduled.",
        "Includes Italian dinner.",
        "Starts after 10:00.",
    ]


def test_trip_request_preserves_natural_language_notes():
    request = CreateTripRequest(
        members=[
            {
                "member_id": "alice",
                "name": "Alice",
                "origin_city": "ORD",
                "budget_usd": 1500,
                "food_restrictions": [],
                "preference_vector": {"food": 0.8},
                "preference_notes": "No clubs.",
                "is_leader": True,
            }
        ],
        group_notes="Relaxed mornings.",
        start_date="2026-07-10",
        end_date="2026-07-12",
    )

    state = _initial_trip_state("trip-1", request)

    assert state["group_notes"] == "Relaxed mornings."
    assert state["members"][0]["preference_notes"] == "No clubs."
    assert state["preference_constraints"] == {}


def test_debug_ui_serves_preference_notes_sample():
    response = TestClient(app).get("/debug/")

    assert response.status_code == 200
    assert "preference_notes" in response.text
    assert "Constraint Satisfaction" in response.text
    assert "Why this day" in response.text
    assert "rationale" in response.text
    assert "constraint_notes" in response.text
