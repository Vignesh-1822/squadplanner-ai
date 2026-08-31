"""Trip refinement routes."""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.nodes.parse_refinement import UnsupportedRefinement, parse_refinement_message
from api.middleware.authz import get_trips_collection, require_leader, require_member
from api.middleware.rate_limit import get_user_key, limiter
from utils.refinement_streaming import stream_refinement_events

router = APIRouter(prefix="/trips", tags=["refinements"])

# Only reject up front for requests that definitively need a brand-new trip. Everything else
# (including unusual phrasing) is handed to the agentic planner during streaming.
_HARD_SCOPE_CODES = {
    "empty_refinement",
    "unsupported_member_change",
    "unsupported_date_change",
    "unsupported_destination_change",
}


class RefineTripRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/{trip_id}/refine")
@limiter.limit("10/hour", key_func=get_user_key)
async def refine_trip(
    request: Request,
    trip_id: str,
    body: RefineTripRequest,
    trip: dict = Depends(require_leader),
    trips: Any = Depends(get_trips_collection),
):
    if not trip.get("final_state") or not trip.get("trip_pitch"):
        raise HTTPException(status_code=409, detail="Trip must complete before it can be refined")

    # Fast-fail only for clearly out-of-scope requests; the agentic planner (run during
    # streaming, with full itinerary context) interprets everything else, including free text
    # the regex parser would not recognize.
    try:
        parse_refinement_message(body.message)
    except UnsupportedRefinement as exc:
        if exc.code in _HARD_SCOPE_CODES:
            raise HTTPException(status_code=422, detail={"message": str(exc), "code": exc.code}) from exc

    refinement_id = str(uuid.uuid4())
    now = _now()
    await trips.update_one(
        {"trip_id": trip_id},
        {
            "$set": {
                f"refinements.{refinement_id}": {
                    "refinement_id": refinement_id,
                    "message": body.message.strip(),
                    "status": "queued",
                    "created_at": now,
                },
                "updated_at": now,
            }
        },
    )

    return {
        "trip_id": trip_id,
        "refinement_id": refinement_id,
        "status": "queued",
        "stream_url": f"/trips/{trip_id}/refinements/{refinement_id}/stream",
    }


@router.get("/{trip_id}/refinements/{refinement_id}/stream")
async def stream_refinement(
    trip_id: str,
    refinement_id: str,
    trip: dict = Depends(require_member),
):
    if not (trip.get("refinements") or {}).get(refinement_id):
        raise HTTPException(status_code=404, detail="Refinement not found")

    return StreamingResponse(
        stream_refinement_events(trip_id, refinement_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
