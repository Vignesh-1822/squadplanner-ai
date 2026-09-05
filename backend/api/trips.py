"""Trip creation and SSE streaming routes."""

import asyncio
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from db.client import get_collection
from services.email_service import send_trip_invite
from utils.streaming import stream_graph_events

logger = logging.getLogger(__name__)

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
    trip_name: str
    created_by: str
    invited_emails: list[str] = Field(default_factory=list)


class InvitedMember(BaseModel):
    email: str
    status: Literal["pending", "joined", "ready", "accepted", "declined"] = "pending"
    name: str | None = None
    avatar_url: str | None = None
    is_leader: bool = False
    has_preferences: bool = False


class TripDetailsResponse(BaseModel):
    trip_id: str
    trip_name: str
    invite_code: str
    status: str
    created_at: str
    expires_at: str
    invited_members: list[InvitedMember]
    ready_count: int
    total_count: int
    all_ready: bool
    can_generate: bool


def _initial_trip_state(trip_id: str, trip_name: str) -> dict:
    return {
        "trip_id": trip_id,
        "trip_name": trip_name,
        "members": [],
        "group_notes": "",
        "start_date": None,
        "end_date": None,
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
        "current_refinement": {},
        "refinement_directives": {},
        "refinement_history": [],
        "decision_log": [],
        "destination_retry_count": 0,
        "hotel_retry_count": 0,
        "error": None,
    }


def _parse_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _isoformat(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _invited_members_from_trip(trip: dict) -> list[dict]:
    invited_members = trip.get("invited_members")
    if isinstance(invited_members, list):
        return [
            {
                "email": member.get("email", ""),
                "status": member.get("status", "pending"),
                "is_leader": bool(member.get("is_leader", False)),
                "has_preferences": bool(member.get("preferences")),
            }
            for member in invited_members
            if isinstance(member, dict) and member.get("email")
        ]

    return [
        {"email": email, "status": "pending", "is_leader": False, "has_preferences": False}
        for email in trip.get("invited_emails", [])
    ]


@router.post("")
async def create_trip(body: CreateTripRequest):
    trip_id = str(uuid.uuid4())
    invite_code = secrets.token_urlsafe(8)
    initial_state = _initial_trip_state(trip_id, body.trip_name)
    now = datetime.now(timezone.utc).isoformat()

    # The creator is a first-class squad member and the trip leader. Guests invited by email
    # start as "pending" until they join and submit preferences.
    invited_members = [
        {"email": body.created_by, "status": "joined", "is_leader": True}
    ]
    for email in body.invited_emails:
        if email and email != body.created_by:
            invited_members.append({"email": email, "status": "pending", "is_leader": False})

    trips = get_collection("trips")
    await trips.insert_one(
        {
            "_id": trip_id,
            "trip_id": trip_id,
            "trip_name": body.trip_name,
            "created_by": body.created_by,
            "invited_emails": body.invited_emails,
            "invited_members": invited_members,
            "invite_code": invite_code,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "initial_state": initial_state,
        }
    )

    if body.invited_emails:
        async def _send_invites():
            for email in body.invited_emails:
                try:
                    await send_trip_invite(email, body.trip_name, invite_code)
                except Exception as exc:
                    logger.error("Failed to send invite to %s: %s", email, exc)

        asyncio.create_task(_send_invites())

    return {
        "trip_id": trip_id,
        "invite_code": invite_code,
        "status": "accepted",
        "stream_url": f"/trips/{trip_id}/stream",
    }
@router.get("")
async def list_trips(email: str | None = None):
    trips_col = get_collection("trips")
    query = {}
    
    if email:
        query["created_by"] = email

    cursor = trips_col.find(query).sort("created_at", -1)
    results = []
    async for doc in cursor:
        initial_state = doc.get("initial_state", {})
        
        invited_members = doc.get("invited_members", [])
        if not invited_members:
            invited_members = [{"email": e, "status": "pending"} for e in doc.get("invited_emails", [])]
            
        start_date = initial_state.get("start_date")
        end_date = initial_state.get("end_date")
        
        results.append({
            "trip_id": doc["trip_id"],
            "trip_name": doc["trip_name"],
            "invite_code": doc["invite_code"],
            "status": doc.get("status", "pending"),
            "created_at": doc["created_at"],
            "invited_members": invited_members,
            "start_date": start_date,
            "end_date": end_date,
            "selected_destination": initial_state.get("selected_destination"),
        })
    return results


@router.get("/{trip_id}", response_model=TripDetailsResponse)
async def get_trip(trip_id: str):
    trips = get_collection("trips")
    trip = await trips.find_one({"trip_id": trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    invited_members = _invited_members_from_trip(trip)
    if "invited_members" not in trip:
        await trips.update_one(
            {"trip_id": trip_id},
            {"$set": {"invited_members": invited_members}},
        )

    users = get_collection("users")
    # One query for the whole squad rather than one per member — the lobby polls this route.
    emails = [m.get("email", "") for m in invited_members if m.get("email")]
    users_by_email = {
        doc["email"]: doc
        async for doc in users.find({"email": {"$in": emails}})
    }

    enriched_members = []
    for member in invited_members:
        email = member.get("email", "")
        status = member.get("status", "pending")
        user_doc = users_by_email.get(email)
        if user_doc:
            name = user_doc.get("name", email.split("@")[0].capitalize())
            avatar_url = user_doc.get("avatar_url", "")
        else:
            name = email.split("@")[0].capitalize()
            avatar_url = ""
        enriched_members.append({
            "email": email,
            "status": status,
            "name": name,
            "avatar_url": avatar_url,
            "is_leader": bool(member.get("is_leader", False)),
            "has_preferences": bool(member.get("has_preferences", False)),
        })

    ready_count = sum(1 for m in enriched_members if m["status"] == "ready")
    total_count = len(enriched_members)
    all_ready = total_count > 0 and ready_count == total_count
    # Strict gate: every invited member must submit before planning can start. all_ready
    # already implies the leader is ready, so no separate leader check is needed.
    can_generate = all_ready and trip.get("status") in (None, "pending", "collecting")

    created_at = trip["created_at"]
    expires_at = _parse_datetime(created_at) + timedelta(hours=24)
    return {
        "trip_id": trip["trip_id"],
        "trip_name": trip["trip_name"],
        "invite_code": trip["invite_code"],
        "status": trip.get("status", "pending"),
        "created_at": _isoformat(created_at),
        "expires_at": expires_at.isoformat(),
        "invited_members": enriched_members,
        "ready_count": ready_count,
        "total_count": total_count,
        "all_ready": all_ready,
        "can_generate": can_generate,
    }


@router.get("/{trip_id}/result")
async def get_trip_result(trip_id: str):
    """Return the completed itinerary payload persisted by the streaming pipeline.

    Lets the itinerary page load (and refinements re-load) a finished trip on a fresh page
    visit, independent of client-side storage.
    """
    trips = get_collection("trips")
    trip = await trips.find_one({"trip_id": trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if not trip.get("itinerary") and not (trip.get("final_state") or {}).get("trip_pitch"):
        raise HTTPException(status_code=409, detail="Trip has not completed yet")

    final_state = trip.get("final_state") or {}
    return {
        "trip_id": trip_id,
        "trip_pitch": trip.get("trip_pitch") or final_state.get("trip_pitch", ""),
        "itinerary": trip.get("itinerary", {}),
        "preference_constraints": trip.get("preference_constraints", {}),
        "constraint_satisfaction": trip.get("constraint_satisfaction", {}),
        "decision_log": trip.get("decision_log", []),
        "refinement_history": trip.get("refinement_history", []),
    }


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
