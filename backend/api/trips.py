"""Trip creation and SSE streaming routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from db.client import get_collection
from utils.streaming import stream_graph_events

router = APIRouter(prefix="/trips", tags=["trips"])


class MemberRequest(BaseModel):
    member_id: str
    name: str
    origin_city: str
    budget_usd: float
    food_restrictions: list[str] = Field(default_factory=list)
    preference_vector: dict[str, float]
    preference_notes: str = ""
    is_leader: bool


class CreateTripRequest(BaseModel):
    members: list[MemberRequest]
    start_date: str
    end_date: str
    group_notes: str = ""


def _initial_trip_state(trip_id: str, request: CreateTripRequest) -> dict:
    return {
        "trip_id": trip_id,
        "members": [member.model_dump() for member in request.members],
        "group_notes": request.group_notes,
        "start_date": request.start_date,
        "end_date": request.end_date,
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


@router.post("")
async def create_trip(request: CreateTripRequest):
    trip_id = str(uuid.uuid4())
    invite_code = trip_id.split("-", 1)[0].upper()
    initial_state = _initial_trip_state(trip_id, request)
    now = datetime.now(timezone.utc).isoformat()

    trips = get_collection("trips")
    await trips.insert_one(
        {
            "_id": trip_id,
            "trip_id": trip_id,
            "invite_code": invite_code,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "initial_state": initial_state,
        }
    )

    return {
        "trip_id": trip_id,
        "invite_code": invite_code,
        "status": "started",
        "stream_url": f"/trips/{trip_id}/stream",
    }


@router.get("/{trip_id}")
async def get_trip(trip_id: str):
    trips = get_collection("trips")
    trip = await trips.find_one({"trip_id": trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.get("/{trip_id}/stream")
async def stream_trip(trip_id: str):
    trips = get_collection("trips")
    trip = await trips.find_one({"trip_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    return StreamingResponse(
        stream_graph_events(trip_id, trip["initial_state"]),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
