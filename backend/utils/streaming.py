"""SSE helpers and graph event streaming."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from langgraph.types import Command

from db.client import get_collection

NODE_PROGRESS_MAP = {
    "parse_input": "Validating trip details...",
    "extract_preference_constraints": "Reading natural-language preferences...",
    "select_destination": "Scoring destinations for your group...",
    "city_selection_hitl": "Waiting for city selection...",
    "dynamic_tool_selection": "Selecting data sources based on group preferences...",
    "parallel_data_fetch": "Fetching flights, activities, and weather...",
    "budget_analysis": "Analysing group budget...",
    "search_hotel": "Finding hotels within budget...",
    "run_itinerary_node": "Building the detailed itinerary...",
    "cluster_by_neighborhood": "Grouping activities by neighbourhood...",
    "build_itinerary": "Building your itinerary...",
    "align_flight_times": "Aligning schedule with flight times...",
    "plan_routes": "Planning routes between activities...",
    "validation_gate": "Validating itinerary...",
    "compute_fairness": "Checking cost fairness across the group...",
    "assemble_output": "Writing your trip pitch...",
}


def format_sse_event(event_type: str, data: dict) -> str:
    """Format a JSON Server-Sent Event frame."""
    payload = json.dumps({"event_type": event_type, "data": data}, default=str)
    return f"data: {payload}\n\n"


def format_sse_comment(comment: str) -> str:
    """Format an SSE comment heartbeat."""
    return f": {comment}\n\n"


async def _get_orchestrator_graph():
    import agent.graph as graph_module

    if graph_module.orchestrator_graph is None:
        await graph_module.initialize_graph()
    return graph_module.orchestrator_graph


def _is_waiting_for_city(snapshot: Any) -> bool:
    return bool(snapshot and "city_selection_hitl" in (snapshot.next or ()))


def _complete_payload(trip_id: str, final_state: dict) -> dict:
    itinerary = {
        "trip_id": trip_id,
        "selected_destination": final_state.get("selected_destination"),
        "selected_destination_coords": final_state.get("selected_destination_coords"),
        "start_date": final_state.get("start_date"),
        "end_date": final_state.get("end_date"),
        "members": final_state.get("members", []),
        "flights": final_state.get("flights", []),
        "hotel": final_state.get("hotel"),
        "days": final_state.get("days", []),
        "weather": final_state.get("weather"),
        "budget_status": final_state.get("budget_status"),
        "fairness_scores": final_state.get("fairness_scores", {}),
        "compatibility_scores": final_state.get("compatibility_scores", {}),
        "fairness_passed": final_state.get("fairness_passed"),
        "preference_constraints": final_state.get("preference_constraints", {}),
        "constraint_satisfaction": final_state.get("constraint_satisfaction", {}),
    }
    return {
        "trip_id": trip_id,
        "trip_pitch": final_state.get("trip_pitch", ""),
        "itinerary": itinerary,
        "preference_constraints": final_state.get("preference_constraints", {}),
        "constraint_satisfaction": final_state.get("constraint_satisfaction", {}),
        "decision_log": final_state.get("decision_log", []),
    }


async def _stream_progress_events(graph: Any, graph_input: Any, config: dict) -> AsyncGenerator[str, None]:
    async for event in graph.astream_events(graph_input, config=config, version="v2"):
        kind = event.get("event")
        name = event.get("name", "")
        if kind == "on_chain_start" and name in NODE_PROGRESS_MAP:
            yield format_sse_event(
                "NODE_PROGRESS",
                {
                    "node": name,
                    "message": NODE_PROGRESS_MAP[name],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )


async def _emit_and_wait_for_city_confirmation(
    graph: Any,
    trip_id: str,
    config: dict,
) -> AsyncGenerator[str, None]:
    trips = get_collection("trips")
    snapshot = await graph.aget_state(config)
    candidates = snapshot.values.get("candidate_destinations", []) if snapshot else []

    await trips.update_one(
        {"trip_id": trip_id},
        {
            "$set": {
                "status": "city_selection",
                "candidate_destinations": candidates,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    yield format_sse_event(
        "HITL_REQUIRED",
        {
            "trip_id": trip_id,
            "candidate_destinations": candidates,
        },
    )

    while True:
        trip = await trips.find_one({"trip_id": trip_id})
        resume_payload = trip.get("city_resume_payload") if trip else None
        if resume_payload:
            await trips.update_one(
                {"trip_id": trip_id},
                {
                    "$set": {
                        "status": "generating",
                        "city_resume_consumed_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )
            async for frame in _stream_progress_events(graph, Command(resume=resume_payload), config):
                yield frame
            return

        yield format_sse_comment("waiting for city confirmation")
        await asyncio.sleep(1)


async def _emit_completion_if_done(graph: Any, trip_id: str, config: dict) -> AsyncGenerator[str, None]:
    snapshot = await graph.aget_state(config)
    if not snapshot or snapshot.next:
        return

    final_state = dict(snapshot.values)
    complete_payload = _complete_payload(trip_id, final_state)
    trips = get_collection("trips")
    await trips.update_one(
        {"trip_id": trip_id},
        {
            "$set": {
                "status": "complete",
                "trip_pitch": final_state.get("trip_pitch"),
                "itinerary": complete_payload["itinerary"],
                "final_state": final_state,
                "preference_constraints": complete_payload["preference_constraints"],
                "constraint_satisfaction": complete_payload["constraint_satisfaction"],
                "decision_log": final_state.get("decision_log", []),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    yield format_sse_event("TRIP_COMPLETE", complete_payload)


async def stream_graph_events(
    trip_id: str,
    initial_state: dict,
) -> AsyncGenerator[str, None]:
    """Stream orchestrator graph progress and completion events for a trip."""
    graph = await _get_orchestrator_graph()
    config = {"configurable": {"thread_id": trip_id}}
    trips = get_collection("trips")

    try:
        trip = await trips.find_one({"trip_id": trip_id})
        if trip and trip.get("status") == "complete":
            yield format_sse_event(
                "TRIP_COMPLETE",
                {
                    "trip_id": trip_id,
                    "trip_pitch": trip.get("trip_pitch", ""),
                    "itinerary": trip.get("itinerary", {}),
                    "preference_constraints": trip.get("preference_constraints", {}),
                    "constraint_satisfaction": trip.get("constraint_satisfaction", {}),
                    "decision_log": trip.get("decision_log", []),
                },
            )
            return

        snapshot = await graph.aget_state(config)
        if _is_waiting_for_city(snapshot):
            async for frame in _emit_and_wait_for_city_confirmation(graph, trip_id, config):
                yield frame
        elif (
            snapshot
            and not snapshot.next
            and snapshot.values.get("trip_id") == trip_id
            and snapshot.values.get("trip_pitch")
        ):
            async for frame in _emit_completion_if_done(graph, trip_id, config):
                yield frame
            return
        else:
            graph_input = None if snapshot and snapshot.values and snapshot.next else initial_state
            await trips.update_one(
                {"trip_id": trip_id},
                {
                    "$set": {
                        "status": "generating",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )
            async for frame in _stream_progress_events(graph, graph_input, config):
                yield frame

            snapshot = await graph.aget_state(config)
            if _is_waiting_for_city(snapshot):
                async for frame in _emit_and_wait_for_city_confirmation(graph, trip_id, config):
                    yield frame

        async for frame in _emit_completion_if_done(graph, trip_id, config):
            yield frame

    except Exception as exc:  # noqa: BLE001
        await trips.update_one(
            {"trip_id": trip_id},
            {
                "$set": {
                    "status": "failed",
                    "error": str(exc),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        yield format_sse_event(
            "ERROR",
            {
                "trip_id": trip_id,
                "message": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
