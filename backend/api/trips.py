"""POST /trips, GET /trips/{id}/stream (SSE)."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["trips"])


@router.post("/trips")
async def create_trip():
    return {"id": "placeholder", "status": "accepted"}


@router.get("/trips/{trip_id}/stream")
async def stream_trip(trip_id: str):
    async def event_gen():
        yield "data: {}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
