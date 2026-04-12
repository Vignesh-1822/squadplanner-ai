"""SerpAPI: flights + hotels with budget gating."""

from typing import Any


async def search_flights(query: dict[str, Any]) -> dict[str, Any]:
    """Flight search; enforce budget limits before returning."""
    return {}


async def search_hotels(query: dict[str, Any]) -> dict[str, Any]:
    """Hotel search; enforce budget limits before returning."""
    return {}
