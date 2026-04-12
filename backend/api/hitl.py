"""POST /trips/{id}/confirm-city — resume graph after human confirmation."""

from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["hitl"])


@router.post("/trips/{trip_id}/confirm-city")
async def confirm_city(trip_id: str, body: dict[str, Any]):
    return {"trip_id": trip_id, "confirmed": True}
