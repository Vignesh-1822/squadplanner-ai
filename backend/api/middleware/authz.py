"""Reusable trip and administrative authorization dependencies."""

from typing import Any

from fastapi import Depends, HTTPException

from api.middleware.auth import get_current_user
from db.client import get_collection


def get_trips_collection() -> Any:
    """Return the trips collection through an override-friendly dependency."""
    return get_collection("trips")


def get_users_collection() -> Any:
    """Return the users collection through an override-friendly dependency."""
    return get_collection("users")


async def _get_trip(trip_id: str, trips: Any) -> dict:
    trip = await trips.find_one({"trip_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


def _is_member(trip: dict, email: str) -> bool:
    members = trip.get("invited_members") or []
    if any(member.get("email") == email for member in members if isinstance(member, dict)):
        return True
    # Trips created before the squad flow only stored these fields.
    return email == trip.get("created_by") or email in (trip.get("invited_emails") or [])


async def require_member(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
    trips: Any = Depends(get_trips_collection),
) -> dict:
    trip = await _get_trip(trip_id, trips)
    if not _is_member(trip, current_user["email"]):
        raise HTTPException(status_code=403, detail="You are not a member of this trip")
    return trip


async def require_leader(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
    trips: Any = Depends(get_trips_collection),
) -> dict:
    trip = await _get_trip(trip_id, trips)
    if trip.get("created_by") != current_user["email"]:
        raise HTTPException(status_code=403, detail="Only the trip leader can perform this action")
    return trip


async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Administrator access required")
    return current_user
