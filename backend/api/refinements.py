"""Trip refinement routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.nodes.parse_refinement import UnsupportedRefinement, parse_refinement_message
from db.client import get_collection
from utils.refinement_streaming import stream_refinement_events

router = APIRouter(prefix="/trips", tags=["refinements"])


class RefineTripRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/{trip_id}/refine")
async def refine_trip(trip_id: str, body: RefineTripRequest):
    trips = get_collection("trips")
    trip = await trips.find_one({"trip_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if not trip.get("final_state") or not trip.get("trip_pitch"):
        raise HTTPException(status_code=409, detail="Trip must complete before it can be refined")

    try:
        parsed = parse_refinement_message(body.message)
    except UnsupportedRefinement as exc:
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
                    "parsed": parsed,
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
async def stream_refinement(trip_id: str, refinement_id: str):
    trips = get_collection("trips")
    trip = await trips.find_one({"trip_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
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
