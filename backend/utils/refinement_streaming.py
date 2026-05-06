"""SSE streaming for post-generation itinerary refinements."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from agent.nodes.parse_refinement import (
    UnsupportedRefinement,
    activity_category_to_fetch,
    build_refinement_state_patch,
    dedupe_new_activities,
    parse_refinement_message,
)
from db.client import get_collection
from tools.google_places import fetch_activities_by_category
from utils.streaming import _complete_payload, _get_orchestrator_graph, _stream_progress_events, format_sse_event


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _nested_get(document: dict, dotted_key: str) -> Any:
    current: Any = document
    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


async def _load_extra_activities(parsed: dict, state: dict) -> list[dict]:
    category = activity_category_to_fetch(parsed, state)
    if not category:
        return []

    fetched = await fetch_activities_by_category(
        destination=state.get("selected_destination") or "",
        coords=state.get("selected_destination_coords") or {"lat": 0.0, "lng": 0.0},
        categories=[category],
    )
    return dedupe_new_activities(state.get("activities", []), fetched)


async def _persist_refinement_complete(
    trips: Any,
    trip_id: str,
    refinement_id: str,
    final_state: dict,
    payload: dict,
    parsed: dict,
) -> None:
    await trips.update_one(
        {"trip_id": trip_id},
        {
            "$set": {
                "status": "complete",
                "trip_pitch": final_state.get("trip_pitch"),
                "itinerary": payload["itinerary"],
                "final_state": final_state,
                "preference_constraints": payload["preference_constraints"],
                "constraint_satisfaction": payload["constraint_satisfaction"],
                "decision_log": final_state.get("decision_log", []),
                "refinement_history": final_state.get("refinement_history", []),
                f"refinements.{refinement_id}.status": "complete",
                f"refinements.{refinement_id}.parsed": parsed,
                f"refinements.{refinement_id}.completed_at": _now(),
                "updated_at": _now(),
            }
        },
    )


async def stream_refinement_events(
    trip_id: str,
    refinement_id: str,
) -> AsyncGenerator[str, None]:
    """Stream a completed-trip refinement by re-entering the existing graph state."""
    graph = await _get_orchestrator_graph()
    trips = get_collection("trips")
    config = {"configurable": {"thread_id": trip_id}}

    try:
        trip = await trips.find_one({"trip_id": trip_id})
        if not trip:
            raise UnsupportedRefinement("Trip not found.", code="trip_not_found")

        refinement = _nested_get(trip, f"refinements.{refinement_id}")
        if not refinement:
            raise UnsupportedRefinement("Refinement not found.", code="refinement_not_found")

        if refinement.get("status") == "complete" and trip.get("final_state"):
            final_state = dict(trip["final_state"])
            payload = _complete_payload(trip_id, final_state)
            payload["refinement"] = {
                "refinement_id": refinement_id,
                "message": refinement.get("message", ""),
                "parsed": refinement.get("parsed", {}),
                "status": "complete",
            }
            yield format_sse_event("REFINEMENT_COMPLETE", payload)
            return

        snapshot = await graph.aget_state(config)
        if not snapshot or not snapshot.values or snapshot.values.get("trip_id") != trip_id:
            raise UnsupportedRefinement("Completed graph checkpoint was not found.", code="checkpoint_not_found")
        if snapshot.next:
            raise UnsupportedRefinement("Trip is still generating and cannot be refined yet.", code="trip_not_complete")
        if not snapshot.values.get("trip_pitch"):
            raise UnsupportedRefinement("Trip must complete before it can be refined.", code="trip_not_complete")

        state = dict(snapshot.values)
        message = refinement.get("message", "")
        parsed = refinement.get("parsed") or parse_refinement_message(message)

        await trips.update_one(
            {"trip_id": trip_id},
            {
                "$set": {
                    "status": "refining",
                    f"refinements.{refinement_id}.status": "streaming",
                    f"refinements.{refinement_id}.parsed": parsed,
                    f"refinements.{refinement_id}.started_at": _now(),
                    "updated_at": _now(),
                }
            },
        )

        yield format_sse_event(
            "REFINEMENT_STARTED",
            {
                "trip_id": trip_id,
                "refinement_id": refinement_id,
                "message": message,
                "timestamp": _now(),
            },
        )
        yield format_sse_event(
            "REFINEMENT_PARSED",
            {
                "trip_id": trip_id,
                "refinement_id": refinement_id,
                "parsed": parsed,
                "timestamp": _now(),
            },
        )

        extra_activities = await _load_extra_activities(parsed, state)
        patch, as_node = build_refinement_state_patch(state, parsed, extra_activities)
        await graph.aupdate_state(config, patch, as_node=as_node)

        async for frame in _stream_progress_events(graph, None, config):
            yield frame

        final_snapshot = await graph.aget_state(config)
        if not final_snapshot or final_snapshot.next:
            raise UnsupportedRefinement("Refinement did not reach a completed graph state.", code="refinement_incomplete")

        final_state = dict(final_snapshot.values)
        payload = _complete_payload(trip_id, final_state)
        payload["refinement"] = {
            "refinement_id": refinement_id,
            "message": message,
            "parsed": parsed,
            "rerun_from": as_node,
            "added_activity_count": len(extra_activities),
            "status": "complete",
        }
        payload["refinement_history"] = final_state.get("refinement_history", [])

        await _persist_refinement_complete(trips, trip_id, refinement_id, final_state, payload, parsed)
        yield format_sse_event("REFINEMENT_COMPLETE", payload)

    except Exception as exc:  # noqa: BLE001
        await trips.update_one(
            {"trip_id": trip_id},
            {
                "$set": {
                    "status": "complete",
                    f"refinements.{refinement_id}.status": "failed",
                    f"refinements.{refinement_id}.error": str(exc),
                    f"refinements.{refinement_id}.failed_at": _now(),
                    "updated_at": _now(),
                }
            },
        )
        yield format_sse_event(
            "ERROR",
            {
                "trip_id": trip_id,
                "refinement_id": refinement_id,
                "message": str(exc),
                "timestamp": _now(),
            },
        )
