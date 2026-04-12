"""Google Routes API wrapper for legs and ETAs."""

from typing import Any


async def compute_route(origin: dict[str, float], destination: dict[str, float]) -> dict[str, Any]:
    """Return route summary (distance, duration, polyline if needed)."""
    return {}
