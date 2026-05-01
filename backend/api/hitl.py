"""Human-in-the-loop graph resume routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.client import get_collection

router = APIRouter(prefix="/trips", tags=["hitl"])


class CityConfirmRequest(BaseModel):
    selected_destination: str
    selected_destination_coords: dict[str, float]


async def _get_orchestrator_graph():
    import agent.graph as graph_module

    if graph_module.orchestrator_graph is None:
        await graph_module.initialize_graph()
    return graph_module.orchestrator_graph


@router.post("/{trip_id}/confirm-city")
async def confirm_city(trip_id: str, body: CityConfirmRequest):
    trips = get_collection("trips")
    trip = await trips.find_one({"trip_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    graph = await _get_orchestrator_graph()
    config = {"configurable": {"thread_id": trip_id}}
    snapshot = await graph.aget_state(config)
    if not snapshot or "city_selection_hitl" not in (snapshot.next or ()):
        raise HTTPException(status_code=400, detail="Trip is not waiting for city selection")

    resume_payload = {
        "selected_destination": body.selected_destination,
        "selected_destination_coords": body.selected_destination_coords,
    }
    await trips.update_one(
        {"trip_id": trip_id},
        {
            "$set": {
                "status": "generating",
                "selected_destination": body.selected_destination,
                "selected_destination_coords": body.selected_destination_coords,
                "city_resume_payload": resume_payload,
                "city_confirmed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {
        "status": "resumed",
        "trip_id": trip_id,
        "destination": body.selected_destination,
    }
