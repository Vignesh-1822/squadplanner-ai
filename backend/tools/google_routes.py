"""Google Routes API — compute routes between lat/lng pairs."""

import logging

import httpx

from agent.state import ActivityResult
from config import settings

logger = logging.getLogger(__name__)

_FALLBACK_ROUTE = {"distance_meters": 0, "duration_seconds": 0, "polyline": "", "mode": "WALK"}


async def get_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    mode: str = "WALK",
) -> dict:
    """Return route summary between two lat/lng points.

    On error returns a zeroed fallback dict.
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://routes.googleapis.com/directions/v2:computeRoutes",
                headers={
                    "X-Goog-Api-Key": settings.google_routes_api_key,
                    "X-Goog-FieldMask": (
                        "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"
                    ),
                },
                json={
                    "origin": {
                        "location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}
                    },
                    "destination": {
                        "location": {"latLng": {"latitude": dest_lat, "longitude": dest_lng}}
                    },
                    "travelMode": mode,
                    "computeAlternativeRoutes": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        route = data["routes"][0]
        duration_str: str = route.get("duration", "0s")
        duration_seconds = int(duration_str.rstrip("s")) if duration_str.endswith("s") else 0

        return {
            "distance_meters": int(route.get("distanceMeters", 0)),
            "duration_seconds": duration_seconds,
            "polyline": route.get("polyline", {}).get("encodedPolyline", ""),
            "mode": mode,
        }

    except Exception as exc:  # noqa: BLE001
        logger.error("get_route error: %s", exc)
        return {**_FALLBACK_ROUTE, "mode": mode}


async def plan_day_routes(activities: list[ActivityResult]) -> dict:
    """Compute consecutive routes for a day's activity list.

    Returns a dict with all route legs and total travel time in minutes.
    """
    if len(activities) < 2:
        return {"routes": [], "total_travel_minutes": 0}

    routes: list[dict] = []
    total_seconds = 0

    for a, b in zip(activities, activities[1:]):
        route = await get_route(a["lat"], a["lng"], b["lat"], b["lng"])
        routes.append(route)
        total_seconds += route["duration_seconds"]

    return {
        "routes": routes,
        "total_travel_minutes": int(total_seconds / 60),
    }


async def plan_stop_routes(stops: list[dict]) -> dict:
    """Compute consecutive routes for ordered stops with lat/lng coordinates."""
    routable_stops = [
        stop for stop in stops if stop.get("lat") is not None and stop.get("lng") is not None
    ]
    if len(routable_stops) < 2:
        return {"routes": [], "total_travel_minutes": 0}

    routes: list[dict] = []
    total_seconds = 0

    for origin, destination in zip(routable_stops, routable_stops[1:]):
        route = await get_route(
            float(origin["lat"]),
            float(origin["lng"]),
            float(destination["lat"]),
            float(destination["lng"]),
        )
        routes.append(
            {
                **route,
                "from_order": origin.get("order"),
                "to_order": destination.get("order"),
                "from_label": origin.get("label"),
                "to_label": destination.get("label"),
            }
        )
        total_seconds += int(route.get("duration_seconds", 0))

    return {
        "routes": routes,
        "total_travel_minutes": int(total_seconds / 60),
    }


if __name__ == "__main__":
    import asyncio

    async def _test() -> None:
        route = await get_route(40.7128, -74.006, 40.758, -73.9855)
        print("Route:", route)

        activities: list[ActivityResult] = [
            {
                "place_id": "A",
                "name": "Central Park",
                "category": "outdoor",
                "address": "New York, NY",
                "lat": 40.7851,
                "lng": -73.9683,
                "price_level": 0,
                "rating": 4.8,
                "tags": ["park"],
            },
            {
                "place_id": "B",
                "name": "MoMA",
                "category": "urban",
                "address": "11 W 53rd St, New York, NY",
                "lat": 40.7614,
                "lng": -73.9776,
                "price_level": 3,
                "rating": 4.6,
                "tags": ["museum"],
            },
        ]
        day = await plan_day_routes(activities)
        print("Day routes:", day)

    asyncio.run(_test())
