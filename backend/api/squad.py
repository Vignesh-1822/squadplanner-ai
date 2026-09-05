"""Squad membership + preference collection + generation trigger.

These routes drive the async squad flow: guests join via invite code, each member submits
their own preferences, and the leader kicks off the agentic pipeline once the squad is ready.
The generation step assembles every ready member into the graph's ``initial_state`` so the
existing SSE stream (``/trips/{trip_id}/stream``) can run the orchestrator unchanged.
"""

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.middleware.auth import get_current_user
from api.middleware.authz import (
    get_trips_collection,
    get_users_collection,
    require_leader,
    require_member,
)
from api.middleware.rate_limit import get_user_key, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips", tags=["squad"])

# Canonical preference dimensions the planning graph understands (see agent/nodes/input_parser.py).
CANONICAL_DIMENSIONS = ("outdoor", "food", "nightlife", "urban", "shopping")
# Frontend "vibe" keys that don't map 1:1 onto a canonical dimension.
VIBE_ALIASES = {"nature": "outdoor", "adventure": "outdoor"}
MAX_TRIP_DAYS = 5


class DateWindow(BaseModel):
    start_date: str
    end_date: str


class PreferencesRequest(BaseModel):
    origin_city: str = Field(min_length=1)
    budget_usd: float = Field(gt=0)
    food_restrictions: list[str] = Field(default_factory=list)
    preference_vector: dict[str, float] = Field(default_factory=dict)
    preference_notes: str = ""
    date_windows: list[DateWindow] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    # Optional leader override; when omitted the group window is computed from member availability.
    start_date: str | None = None
    end_date: str | None = None
    group_notes: str | None = None


class JoinTripRequest(BaseModel):
    invite_code: str = Field(min_length=1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonicalize_vector(raw: dict[str, float] | None) -> dict[str, float]:
    """Map arbitrary vibe keys (0-100 or 0-1) onto the canonical 0-1 preference vector."""
    sums = {dim: 0.0 for dim in CANONICAL_DIMENSIONS}
    counts = {dim: 0 for dim in CANONICAL_DIMENSIONS}
    for key, value in (raw or {}).items():
        dim = VIBE_ALIASES.get(str(key).lower(), str(key).lower())
        if dim not in sums:
            continue
        try:
            num = float(value)
        except (TypeError, ValueError):
            continue
        if num > 1.0:  # accept 0-100 sliders
            num /= 100.0
        sums[dim] += max(0.0, min(num, 1.0))
        counts[dim] += 1
    return {dim: (sums[dim] / counts[dim] if counts[dim] else 0.0) for dim in CANONICAL_DIMENSIONS}


def _member_id_from_email(email: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", email.split("@")[0].lower()).strip("_") or "traveler"
    candidate = base
    suffix = 1
    while candidate in taken:
        suffix += 1
        candidate = f"{base}_{suffix}"
    taken.add(candidate)
    return candidate


def _display_name(email: str, user_doc: dict | None) -> str:
    if user_doc and user_doc.get("name"):
        return user_doc["name"]
    return email.split("@")[0].capitalize()


async def _get_trip_or_404(trip_id: str, trips: Any) -> dict:
    trip = await trips.find_one({"trip_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


def _summarize_members(invited_members: list[dict]) -> list[dict]:
    return [
        {
            "email": m.get("email", ""),
            "status": m.get("status", "pending"),
            "is_leader": bool(m.get("is_leader", False)),
            "has_preferences": bool(m.get("preferences")),
        }
        for m in invited_members
        if isinstance(m, dict) and m.get("email")
    ]


@router.get("/by-invite/{invite_code}")
async def get_trip_by_invite(
    invite_code: str,
    trips: Any = Depends(get_trips_collection),
    users: Any = Depends(get_users_collection),
):
    """Public lookup so a guest opening an invite link can see what they're joining."""
    trip = await trips.find_one({"invite_code": invite_code})
    if not trip:
        raise HTTPException(status_code=404, detail="Invite not found")

    leader_email = trip.get("created_by", "")
    leader = await users.find_one({"email": leader_email}) if leader_email else None
    members = trip.get("invited_members") or []
    member_count = len([member for member in members if isinstance(member, dict)])
    if not member_count:
        legacy_emails = set(trip.get("invited_emails") or [])
        if leader_email:
            legacy_emails.add(leader_email)
        member_count = len(legacy_emails)

    return {
        "trip_id": trip["trip_id"],
        "trip_name": trip["trip_name"],
        "invite_code": invite_code,
        "member_count": member_count,
        "leader_name": _display_name(leader_email, leader),
    }


@router.post("/{trip_id}/join")
async def join_trip(
    trip_id: str,
    body: JoinTripRequest,
    current_user: dict = Depends(get_current_user),
    trips: Any = Depends(get_trips_collection),
):
    """Authenticated user joins the squad. Invited guests flip pending -> joined; anyone else
    who has the invite link is added as a new joined member."""
    trip = await _get_trip_or_404(trip_id, trips)
    if body.invite_code != trip.get("invite_code"):
        raise HTTPException(status_code=403, detail="Invalid invite code")

    email = current_user["email"]
    members = trip.get("invited_members", [])

    existing = next((m for m in members if m.get("email") == email), None)
    if existing:
        if existing.get("status") == "pending":
            existing["status"] = "joined"
    else:
        members.append({"email": email, "status": "joined", "is_leader": False})

    await trips.update_one(
        {"trip_id": trip_id},
        {"$set": {"invited_members": members, "updated_at": _now()}},
    )
    return {"trip_id": trip_id, "status": "joined", "invited_members": _summarize_members(members)}


@router.post("/{trip_id}/preferences")
async def submit_preferences(
    trip_id: str,
    body: PreferencesRequest,
    current_user: dict = Depends(get_current_user),
    trip: dict = Depends(require_member),
    trips: Any = Depends(get_trips_collection),
):
    """A member submits their own preferences and becomes 'ready'."""
    if trip.get("status") not in (None, "pending", "collecting"):
        raise HTTPException(status_code=409, detail="Trip has already started planning")

    email = current_user["email"]
    members = trip.get("invited_members", [])

    preferences = {
        "origin_city": body.origin_city.strip().upper(),
        "budget_usd": float(body.budget_usd),
        "food_restrictions": [f.strip() for f in body.food_restrictions if f.strip()],
        "preference_vector": canonicalize_vector(body.preference_vector),
        "preference_notes": body.preference_notes.strip(),
        "date_windows": [w.model_dump() for w in body.date_windows],
        "submitted_at": _now(),
    }

    existing = next((m for m in members if m.get("email") == email), None)
    if existing:
        existing["status"] = "ready"
        existing["preferences"] = preferences
    else:
        members.append({
            "email": email,
            "status": "ready",
            "is_leader": False,
            "preferences": preferences,
        })

    await trips.update_one(
        {"trip_id": trip_id},
        {"$set": {"invited_members": members, "status": "collecting", "updated_at": _now()}},
    )
    return {"trip_id": trip_id, "status": "ready", "invited_members": _summarize_members(members)}


def _compute_group_window(members: list[dict]) -> tuple[str, str]:
    """Find the earliest date range that falls inside at least one window of every member."""
    per_member_days: list[set[date]] = []
    for member in members:
        available: set[date] = set()
        for window in member.get("preferences", {}).get("date_windows", []):
            try:
                start = date.fromisoformat(window["start_date"])
                end = date.fromisoformat(window["end_date"])
            except (KeyError, ValueError):
                continue
            if end < start:
                start, end = end, start
            cursor = start
            while cursor <= end:
                available.add(cursor)
                cursor += timedelta(days=1)
        per_member_days.append(available)

    if any(not days for days in per_member_days):
        raise HTTPException(
            status_code=422,
            detail="Every member must provide at least one date window before generating.",
        )

    common = set.intersection(*per_member_days)
    if not common:
        raise HTTPException(
            status_code=422,
            detail="No overlapping availability across the squad. Align your date windows first.",
        )

    ordered = sorted(common)
    # Earliest contiguous run within the common availability.
    run_start = ordered[0]
    run_end = ordered[0]
    for day in ordered[1:]:
        if day == run_end + timedelta(days=1):
            run_end = day
        else:
            break
    run_end = min(run_end, run_start + timedelta(days=MAX_TRIP_DAYS - 1))
    return run_start.isoformat(), run_end.isoformat()


@router.post("/{trip_id}/generate")
@limiter.limit("3/hour", key_func=get_user_key)
async def generate_trip(
    request: Request,
    trip_id: str,
    body: GenerateRequest,
    trip: dict = Depends(require_leader),
    trips: Any = Depends(get_trips_collection),
    users: Any = Depends(get_users_collection),
):
    """Leader-only: assemble ready members into the graph's initial_state and unlock streaming."""
    if trip.get("status") not in (None, "pending", "collecting"):
        raise HTTPException(status_code=409, detail="Trip has already started planning")

    invited_members = trip.get("invited_members", [])
    ready = [m for m in invited_members if m.get("preferences")]
    if not ready:
        raise HTTPException(status_code=422, detail="No members have submitted preferences yet")
    if len(ready) > 8:
        raise HTTPException(status_code=422, detail="Trips support at most 8 members")

    # Exactly one leader is required by the planner. Normalize to the creator.
    leaders = [m for m in ready if m.get("is_leader")]
    if not leaders:
        raise HTTPException(status_code=422, detail="The trip leader must submit preferences before generating")

    taken_ids: set[str] = set()
    graph_members: list[dict] = []
    all_notes: list[str] = []
    for member in ready:
        email = member["email"]
        prefs = member["preferences"]
        user_doc = await users.find_one({"email": email})
        graph_members.append({
            "member_id": _member_id_from_email(email, taken_ids),
            "name": _display_name(email, user_doc),
            "origin_city": prefs["origin_city"],
            "budget_usd": float(prefs["budget_usd"]),
            "food_restrictions": prefs.get("food_restrictions", []),
            "preference_vector": prefs["preference_vector"],
            "preference_notes": prefs.get("preference_notes", ""),
            "is_leader": bool(member.get("is_leader")),
        })
        if prefs.get("preference_notes"):
            all_notes.append(f"{_display_name(email, user_doc)}: {prefs['preference_notes']}")

    # Keep exactly one leader flag set (first leader wins).
    seen_leader = False
    for gm in graph_members:
        if gm["is_leader"] and not seen_leader:
            seen_leader = True
        else:
            gm["is_leader"] = False

    if body.start_date and body.end_date:
        start_date, end_date = body.start_date, body.end_date
    else:
        start_date, end_date = _compute_group_window(ready)

    duration = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1
    group_notes = body.group_notes or " ".join(all_notes)

    initial_state = dict(trip.get("initial_state") or {})
    initial_state.update({
        "trip_id": trip_id,
        "members": graph_members,
        "group_notes": group_notes,
        "start_date": start_date,
        "end_date": end_date,
        "trip_duration_days": duration,
    })

    await trips.update_one(
        {"trip_id": trip_id},
        {
            "$set": {
                "initial_state": initial_state,
                "status": "generating",
                "start_date": start_date,
                "end_date": end_date,
                "updated_at": _now(),
            }
        },
    )

    return {
        "trip_id": trip_id,
        "status": "generating",
        "member_count": len(graph_members),
        "start_date": start_date,
        "end_date": end_date,
        "stream_url": f"/trips/{trip_id}/stream",
    }
