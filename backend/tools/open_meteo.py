"""Open-Meteo — free weather forecasts and historical data (no API key required)."""

import logging
from datetime import date

import httpx

from agent.state import WeatherResult

logger = logging.getLogger(__name__)

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def _pick_url(start_date: str) -> str:
    """Use the archive API for past dates, forecast API for future/near-present."""
    try:
        start = date.fromisoformat(start_date)
        if start < date.today():
            return _ARCHIVE_URL
    except ValueError:
        pass
    return _FORECAST_URL


def _temp_label(avg_c: float) -> str:
    if avg_c < 5:
        return "Cold"
    if avg_c < 15:
        return "Cool"
    if avg_c <= 25:
        return "Mild"
    return "Warm"


def _precip_label(total_mm: float) -> str:
    if total_mm < 5:
        return "dry conditions"
    if total_mm <= 20:
        return "light rain expected"
    return "significant rain expected"


def _zeroed_result(destination_name: str, start_date: str, end_date: str) -> WeatherResult:
    return WeatherResult(
        destination=destination_name,
        date_range=f"{start_date} to {end_date}",
        avg_temp_c=0.0,
        precipitation_mm=0.0,
        summary="Weather data unavailable",
    )


async def fetch_weather(
    lat: float,
    lng: float,
    start_date: str,
    end_date: str,
    destination_name: str,
) -> WeatherResult:
    """Fetch daily weather for a date range and return a WeatherResult."""
    try:
        url = _pick_url(start_date)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url,
                params={
                    "latitude": lat,
                    "longitude": lng,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                    "start_date": start_date,
                    "end_date": end_date,
                    "timezone": "auto",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        daily = data.get("daily", {})
        temps_max: list[float] = daily.get("temperature_2m_max") or []
        temps_min: list[float] = daily.get("temperature_2m_min") or []
        precip: list[float] = daily.get("precipitation_sum") or []

        all_temps = [t for t in temps_max + temps_min if t is not None]
        avg_temp = round(sum(all_temps) / len(all_temps), 1) if all_temps else 0.0
        total_precip = round(sum(p for p in precip if p is not None), 1)

        summary = f"{_temp_label(avg_temp)} ({avg_temp}°C avg), {_precip_label(total_precip)}"

        return WeatherResult(
            destination=destination_name,
            date_range=f"{start_date} to {end_date}",
            avg_temp_c=avg_temp,
            precipitation_mm=total_precip,
            summary=summary,
        )

    except Exception as exc:  # noqa: BLE001
        logger.error("fetch_weather error: %s", exc)
        return _zeroed_result(destination_name, start_date, end_date)


if __name__ == "__main__":
    import asyncio

    async def _test() -> None:
        result = await fetch_weather(
            lat=40.7128,
            lng=-74.006,
            start_date="2025-06-01",
            end_date="2025-06-07",
            destination_name="New York City",
        )
        print("Weather:", result)

    asyncio.run(_test())
