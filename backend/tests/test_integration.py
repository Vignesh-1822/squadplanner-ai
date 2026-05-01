"""Live-gated full graph integration test."""

import json
import os
import uuid
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv
from langgraph.types import Command

from config import configure_langsmith


load_dotenv()
RUN_LIVE_INTEGRATION = os.getenv("RUN_LIVE_INTEGRATION", "").lower() == "true"
LIVE_TRIP_INPUT_FILE = os.getenv("LIVE_TRIP_INPUT_FILE")
LIVE_TRIP_INPUT_JSON = os.getenv("LIVE_TRIP_INPUT_JSON")
LIVE_DESTINATION_INDEX = os.getenv("LIVE_DESTINATION_INDEX", "0")
ARTIFACT_DIR = Path("tests/artifacts")


def _base_initial_state(trip_id: str) -> dict[str, Any]:
    return {
        "trip_id": trip_id,
        "members": [],
        "group_notes": "",
        "start_date": "",
        "end_date": "",
        "trip_duration_days": 0,
        "preference_conflicts": [],
        "preference_constraints": {},
        "constraint_satisfaction": {},
        "group_preference_vector": {},
        "destination_preference_vector": {},
        "active_tool_categories": [],
        "candidate_destinations": [],
        "selected_destination": None,
        "selected_destination_coords": None,
        "flights": [],
        "activities": [],
        "weather": None,
        "budget_status": None,
        "budget_ceiling_hotel_usd": None,
        "hotel": None,
        "days": [],
        "fairness_scores": {},
        "compatibility_scores": {},
        "fairness_passed": False,
        "trip_pitch": None,
        "decision_log": [],
        "destination_retry_count": 0,
        "hotel_retry_count": 0,
        "error": None,
    }


def _mock_trip_payload() -> dict[str, Any]:
    return {
        "members": [
            {
                "member_id": "alice",
                "name": "Alice",
                "origin_city": "ORD",
                "budget_usd": 1500.0,
                "food_restrictions": ["vegetarian"],
                "preference_notes": "Hates early mornings, no clubs, wants Italian food at least once.",
                "preference_vector": {
                    "outdoor": 0.8,
                    "food": 0.7,
                    "nightlife": 0.2,
                    "urban": 0.6,
                    "shopping": 0.1,
                },
                "is_leader": True,
            },
            {
                "member_id": "bob",
                "name": "Bob",
                "origin_city": "ATL",
                "budget_usd": 1200.0,
                "food_restrictions": [],
                "preference_notes": "Likes relaxed days with good meals and no overpacked schedule.",
                "preference_vector": {
                    "outdoor": 0.5,
                    "food": 0.8,
                    "nightlife": 0.6,
                    "urban": 0.4,
                    "shopping": 0.3,
                },
                "is_leader": False,
            },
            {
                "member_id": "carol",
                "name": "Carol",
                "origin_city": "LAX",
                "budget_usd": 2000.0,
                "food_restrictions": [],
                "preference_notes": "Interested in scenic walks and urban neighborhoods, but not late-night clubbing.",
                "preference_vector": {
                    "outdoor": 0.6,
                    "food": 0.6,
                    "nightlife": 0.4,
                    "urban": 0.7,
                    "shopping": 0.5,
                },
                "is_leader": False,
            },
        ],
        "group_notes": "Keep the trip relaxed and avoid rushed mornings.",
        "start_date": "2026-07-10",
        "end_date": "2026-07-13",
    }


def _load_trip_payload() -> dict[str, Any]:
    if LIVE_TRIP_INPUT_JSON:
        return json.loads(LIVE_TRIP_INPUT_JSON)

    if LIVE_TRIP_INPUT_FILE:
        return json.loads(Path(LIVE_TRIP_INPUT_FILE).read_text(encoding="utf-8"))

    return _mock_trip_payload()


def _initial_state(trip_id: str) -> dict[str, Any]:
    payload = _load_trip_payload()
    state = _base_initial_state(trip_id)
    state.update(payload)
    state["trip_id"] = trip_id
    return state


def _destination_index() -> int:
    try:
        return max(0, int(LIVE_DESTINATION_INDEX))
    except ValueError:
        return 0


def _write_artifacts(trip_id: str, final_state: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = ARTIFACT_DIR / f"{trip_id}.json"
    markdown_path = ARTIFACT_DIR / f"{trip_id}.md"

    json_path.write_text(
        json.dumps(final_state, indent=2, default=str),
        encoding="utf-8",
    )

    decision_log = "\n".join(
        f"- [{entry.get('node')}] {entry.get('decision')}"
        for entry in final_state.get("decision_log", [])
    )
    markdown_path.write_text(
        "\n\n".join(
            [
                f"# {final_state.get('selected_destination', 'Trip')} Integration Run",
                final_state.get("trip_pitch") or "",
                "## Hotel",
                json.dumps(final_state.get("hotel"), indent=2, default=str),
                "## Days",
                json.dumps(final_state.get("days"), indent=2, default=str),
                "## Flights",
                json.dumps(final_state.get("flights"), indent=2, default=str),
                "## Constraint Satisfaction",
                json.dumps(final_state.get("constraint_satisfaction"), indent=2, default=str),
                "## Decision Log",
                decision_log,
            ]
        ),
        encoding="utf-8",
    )

    print(f"\nArtifacts saved:\n  {json_path}\n  {markdown_path}")


@pytest.mark.skipif(
    not RUN_LIVE_INTEGRATION,
    reason="Set RUN_LIVE_INTEGRATION=true to spend live LLM/tool API quota.",
)
@pytest.mark.asyncio
async def test_full_trip_integration_live():
    """Run the full graph against live dependencies, including HITL resume."""
    configure_langsmith()

    import agent.graph as graph_module
    from db.checkpointer import get_checkpointer

    trip_id = f"integration-test-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": trip_id}}
    initial_state = _initial_state(trip_id)

    await graph_module.initialize_graph()
    orchestrator_graph = graph_module.orchestrator_graph
    assert orchestrator_graph is not None

    try:
        print("\n=== Live Trip Input ===")
        print(f"Members: {len(initial_state['members'])}")
        print(f"Dates: {initial_state['start_date']} to {initial_state['end_date']}")
        if LIVE_TRIP_INPUT_FILE:
            print(f"Input file: {LIVE_TRIP_INPUT_FILE}")
        elif LIVE_TRIP_INPUT_JSON:
            print("Input source: LIVE_TRIP_INPUT_JSON")
        else:
            print("Input source: built-in mock fixture")

        print("\n=== Phase 1: Running to HITL interrupt ===")
        async for event in orchestrator_graph.astream_events(
            initial_state,
            config=config,
            version="v2",
        ):
            if event["event"] == "on_chain_start":
                print(f"  -> Node: {event['name']}")

        snapshot = await orchestrator_graph.aget_state(config)
        assert snapshot is not None, "Graph should have saved state at interrupt"
        assert "city_selection_hitl" in (snapshot.next or ()), "Graph should pause at city selection"

        candidates = snapshot.values.get("candidate_destinations", [])
        assert len(candidates) == 5, f"Expected 5 candidates, got {len(candidates)}"
        for index, candidate in enumerate(candidates):
            print(f"{index}: {candidate['name']} (score: {candidate['score']:.3f})")

        choice_index = min(_destination_index(), len(candidates) - 1)
        chosen = candidates[choice_index]
        print(f"\nSelected destination: {chosen['name']} (index: {choice_index}, score: {chosen['score']:.3f})")
        print(f"LLM reasoning: {chosen['llm_reasoning']}")

        print("\n=== Phase 2: Confirming city and resuming ===")
        resume_payload = {
            "selected_destination": chosen["name"],
            "selected_destination_coords": chosen["coords"],
        }

        print("\n=== Phase 3: Running to completion ===")
        async for event in orchestrator_graph.astream_events(
            Command(resume=resume_payload),
            config=config,
            version="v2",
        ):
            if event["event"] == "on_chain_start" and event["name"] in {
                "dynamic_tool_selection",
                "parallel_data_fetch",
                "budget_analysis",
                "search_hotel",
                "run_itinerary_node",
                "compute_fairness",
                "assemble_output",
            }:
                print(f"  -> Node: {event['name']}")

        final_snapshot = await orchestrator_graph.aget_state(config)
        final_state = final_snapshot.values

        print("\n=== Assertions ===")
        assert final_state.get("trip_pitch"), "trip_pitch should be non-empty"
        print(f"OK trip_pitch generated ({len(final_state['trip_pitch'])} chars)")

        assert len(final_state.get("days", [])) > 0, "days should have at least 1 entry"
        print(f"OK days: {len(final_state['days'])} days built")

        assert len(final_state.get("decision_log", [])) >= 8, "Expected at least 8 decision log entries"
        print(f"OK decision_log: {len(final_state['decision_log'])} entries")

        assert final_state.get("hotel") is not None, "hotel should be populated"
        print(f"OK hotel: {final_state['hotel']['name']}")

        assert "fairness_passed" in final_state, "fairness_passed should be set"
        print(f"OK fairness_passed: {final_state['fairness_passed']}")

        assert len(final_state.get("flights", [])) == len(initial_state["members"]), "Should have one flight per member"
        print(f"OK flights: {len(final_state['flights'])} found")

        _write_artifacts(trip_id, final_state)

        print("\n=== Trip Pitch Preview ===")
        print(final_state["trip_pitch"][:500] + "...")

        print("\n=== Decision Log ===")
        for entry in final_state["decision_log"]:
            print(f"  [{entry['node']}] {entry['decision']}")

    finally:
        checkpointer = await get_checkpointer()
        try:
            await checkpointer.adelete_thread(trip_id)
        except Exception as exc:  # noqa: BLE001
            print(f"Checkpoint cleanup skipped: {exc}")
