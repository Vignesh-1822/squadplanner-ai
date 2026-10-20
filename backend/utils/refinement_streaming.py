"""SSE streaming for post-generation itinerary refinements."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from agent.nodes.parse_refinement import (
    UnsupportedRefinement,
    activity_category_to_fetch,
    build_refinement_state_patch,
    dedupe_new_activities,
    named_place_to_fetch,
    parse_refinement_message,
)
from agent.nodes.refine_agent import build_agentic_state_patch, plan_refinement_agentic
from db.client import get_collection
from evals.telemetry.usage import UsageTracker, telemetry_inc_fields
from evals.tracing import build_callbacks, member_emails_from_trip
from tools.google_places import fetch_activities_by_category, find_place_by_text
from utils.streaming import _complete_payload, _get_orchestrator_graph, _stream_progress_events, format_sse_event

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _resolve_refinement(
    message: str, state: dict, config: dict | None = None
) -> tuple[dict, dict, str, list[dict]]:
    """Plan a refinement, returning (parsed_event, state_patch, rerun_node, extra_activities).

    Tries the agentic Haiku planner first so any free-text phrasing is understood and every
    concrete place is grounded via tools. A definitive out-of-scope verdict propagates as an
    error; any other agent failure falls back to the deterministic regex parser so refinements
    keep working offline / when the LLM is unavailable.
    """
    try:
        plan, resolved = await plan_refinement_agentic(message, state, config=config)
    except UnsupportedRefinement:
        raise
    except Exception as exc:  # noqa: BLE001 - any agent failure degrades gracefully
        logger.warning("Agentic refinement failed (%s); falling back to regex parser", exc)
        parsed = parse_refinement_message(message)
        extra = await _load_extra_activities(parsed, state)
        patch, as_node = build_refinement_state_patch(state, parsed, extra)
        return {**parsed, "engine": "regex"}, patch, as_node, extra

    patch, as_node = build_agentic_state_patch(state, plan, message, resolved)
    parsed_event = {
        "engine": "agentic",
        "message": plan.get("summary") or message,
        "intent": "agentic_refinement",
        "rerun_from": as_node,
        "plan": plan,
    }
    return parsed_event, patch, as_node, resolved


def _nested_get(document: dict, dotted_key: str) -> Any:
    current: Any = document
    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


async def _load_extra_activities(parsed: dict, state: dict) -> list[dict]:
    destination = state.get("selected_destination") or ""
    coords = state.get("selected_destination_coords") or {"lat": 0.0, "lng": 0.0}
    existing = list(state.get("activities", []))
    extra: list[dict] = []

    # Pull in the exact named place a swap requested (e.g. "Sears Tower") so it actually
    # enters the activity pool and can be matched into the rendered itinerary stops.
    named = named_place_to_fetch(parsed, state)
    if named:
        place = await find_place_by_text(query=named, destination=destination, coords=coords)
        if place:
            extra.extend(dedupe_new_activities(existing, [dict(place)]))

    category = activity_category_to_fetch(parsed, state)
    if category:
        fetched = await fetch_activities_by_category(
            destination=destination,
            coords=coords,
            categories=[category],
        )
        extra.extend(dedupe_new_activities(existing + extra, fetched))

    return extra


async def _persist_refinement_complete(
    trips: Any,
    trip_id: str,
    refinement_id: str,
    final_state: dict,
    payload: dict,
    parsed: dict,
    telemetry_segment: dict,
) -> None:
    update: dict[str, Any] = {
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
    }
    increments = telemetry_inc_fields(telemetry_segment)
    if increments:
        update["$inc"] = increments
    await trips.update_one(
        {"trip_id": trip_id},
        update,
    )


async def stream_refinement_events(
    trip_id: str,
    refinement_id: str,
) -> AsyncGenerator[str, None]:
    """Stream a completed-trip refinement by re-entering the existing graph state."""
    graph = await _get_orchestrator_graph()
    trips = get_collection("trips")
    usage_tracker: UsageTracker | None = None

    try:
        trip = await trips.find_one({"trip_id": trip_id})
        if not trip:
            raise UnsupportedRefinement("Trip not found.", code="trip_not_found")
        emails = member_emails_from_trip(trip)
        callbacks, usage_tracker = build_callbacks(trip_id, emails)
        config = {
            "configurable": {"thread_id": trip_id},
            "callbacks": callbacks,
            "metadata": {"trip_id": trip_id, "refinement_id": refinement_id},
        }

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

        yield format_sse_event(
            "REFINEMENT_STARTED",
            {
                "trip_id": trip_id,
                "refinement_id": refinement_id,
                "message": message,
                "timestamp": _now(),
            },
        )

        parsed, patch, as_node, extra_activities = await _resolve_refinement(message, state, config)

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
            "REFINEMENT_PARSED",
            {
                "trip_id": trip_id,
                "refinement_id": refinement_id,
                "parsed": parsed,
                "timestamp": _now(),
            },
        )

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

        telemetry_segment = usage_tracker.drain()
        await _persist_refinement_complete(
            trips,
            trip_id,
            refinement_id,
            final_state,
            payload,
            parsed,
            telemetry_segment,
        )
        yield format_sse_event("REFINEMENT_COMPLETE", payload)

    except Exception as exc:  # noqa: BLE001
        update: dict[str, Any] = {
            "$set": {
                "status": "complete",
                f"refinements.{refinement_id}.status": "failed",
                f"refinements.{refinement_id}.error": str(exc),
                f"refinements.{refinement_id}.failed_at": _now(),
                "updated_at": _now(),
            }
        }
        if usage_tracker:
            increments = telemetry_inc_fields(usage_tracker.drain())
            if increments:
                update["$inc"] = increments
        await trips.update_one(
            {"trip_id": trip_id},
            update,
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
