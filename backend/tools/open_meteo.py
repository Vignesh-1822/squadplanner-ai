"""Open-Meteo — weather forecasts (no API key)."""

from typing import Any


async def get_forecast(lat: float, lon: float, start: str, end: str) -> dict[str, Any]:
    """Fetch weather for a date range at coordinates."""
    return {}
