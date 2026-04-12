"""Google Places — dynamic category fetch for activities / POIs."""

from typing import Any


async def fetch_places_nearby(lat: float, lng: float, category: str) -> list[dict[str, Any]]:
    """Return place results for a category near a point."""
    return []
