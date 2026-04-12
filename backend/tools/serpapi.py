"""SerpAPI: flights + hotels with monthly budget gating."""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from agent.state import FlightResult, HotelResult
from config import settings
from db.client import get_collection

logger = logging.getLogger(__name__)

_CACHE_TTL_HOURS = 12


class SerpAPILimitReached(Exception):
    pass


async def check_and_increment_serpapi_budget() -> bool:
    """Atomically increment this month's SerpAPI call count.

    Returns True if the call is allowed.
    Raises SerpAPILimitReached if the monthly hard limit has been hit.
    """
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    collection = get_collection("api_cache")
    doc = await collection.find_one_and_update(
        {
            "type": "serpapi_usage",
            "month": current_month,
            "calls_used": {"$lt": settings.serpapi_monthly_hard_limit},
        },
        {"$inc": {"calls_used": 1}},
        upsert=True,
        return_document=True,
    )
    if doc is None:
        raise SerpAPILimitReached(
            f"SerpAPI monthly hard limit of {settings.serpapi_monthly_hard_limit} reached for {current_month}."
        )
    return True


def _estimated_flight(origin: str, destination: str, depart_date: str, return_date: str) -> FlightResult:
    return FlightResult(
        member_id="",
        origin=origin,
        destination=destination,
        price_usd=300.0,
        airline="Estimated",
        depart_time=f"{depart_date}T08:00:00",
        return_time=f"{return_date}T18:00:00",
        is_estimated=True,
    )


def _estimated_hotel(destination: str) -> HotelResult:
    return HotelResult(
        name="Estimated Hotel",
        address=destination,
        price_per_night_usd=120.0,
        total_price_usd=0.0,
        rating=0.0,
        is_estimated=True,
    )


async def search_flights(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str,
    adults: int = 1,
) -> FlightResult:
    """Return the cheapest available flight; fall back to estimate on errors or quota."""
    cache_key = f"flights:{origin}:{destination}:{depart_date}:{return_date}:{adults}"
    collection = get_collection("api_cache")

    try:
        # cache read (best-effort)
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=_CACHE_TTL_HOURS)
            cached = await collection.find_one({"key": cache_key, "cached_at": {"$gte": cutoff}})
            if cached:
                cached.pop("_id", None)
                cached.pop("key", None)
                cached.pop("cached_at", None)
                return FlightResult(**cached)
        except Exception as cache_exc:  # noqa: BLE001
            logger.warning("Flight cache read failed (continuing without cache): %s", cache_exc)

        try:
            await check_and_increment_serpapi_budget()
        except SerpAPILimitReached:
            logger.warning("SerpAPI limit reached — returning estimated flight for %s→%s", origin, destination)
            return _estimated_flight(origin, destination, depart_date, return_date)

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://serpapi.com/search",
                params={
                    "engine": "google_flights",
                    "departure_id": origin,
                    "arrival_id": destination,
                    "outbound_date": depart_date,
                    "return_date": return_date,
                    "adults": adults,
                    "api_key": settings.serpapi_key,
                    "currency": "USD",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        flights = data.get("best_flights") or data.get("other_flights") or []
        if not flights:
            return _estimated_flight(origin, destination, depart_date, return_date)

        best = flights[0]
        legs = best.get("flights", [{}])
        first_leg = legs[0]
        last_leg = legs[-1]

        result = FlightResult(
            member_id="",
            origin=origin,
            destination=destination,
            price_usd=float(best.get("price", 300.0)),
            airline=first_leg.get("airline", "Unknown"),
            depart_time=first_leg.get("departure_airport", {}).get("time", f"{depart_date}T08:00:00"),
            return_time=last_leg.get("arrival_airport", {}).get("time", f"{return_date}T18:00:00"),
            is_estimated=False,
        )

        try:
            doc = {**result, "key": cache_key, "cached_at": datetime.now(timezone.utc)}
            await collection.update_one({"key": cache_key}, {"$set": doc}, upsert=True)
        except Exception as write_exc:  # noqa: BLE001
            logger.warning("Flight cache write failed: %s", write_exc)
        return result

    except Exception as exc:  # noqa: BLE001
        logger.error("search_flights error: %s", exc)
        return _estimated_flight(origin, destination, depart_date, return_date)


async def search_hotels(
    destination: str,
    check_in: str,
    check_out: str,
    budget_ceiling_usd: float,
) -> HotelResult:
    """Return the best hotel under budget; fall back to estimate on errors or quota."""
    cache_key = f"hotels:{destination}:{check_in}:{check_out}:{int(budget_ceiling_usd)}"
    collection = get_collection("api_cache")

    try:
        # cache read (best-effort)
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=_CACHE_TTL_HOURS)
            cached = await collection.find_one({"key": cache_key, "cached_at": {"$gte": cutoff}})
            if cached:
                cached.pop("_id", None)
                cached.pop("key", None)
                cached.pop("cached_at", None)
                return HotelResult(**cached)
        except Exception as cache_exc:  # noqa: BLE001
            logger.warning("Hotel cache read failed (continuing without cache): %s", cache_exc)

        try:
            await check_and_increment_serpapi_budget()
        except SerpAPILimitReached:
            logger.warning("SerpAPI limit reached — returning estimated hotel for %s", destination)
            return _estimated_hotel(destination)

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://serpapi.com/search",
                params={
                    "engine": "google_hotels",
                    "q": f"hotels in {destination}",
                    "check_in_date": check_in,
                    "check_out_date": check_out,
                    "api_key": settings.serpapi_key,
                    "currency": "USD",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        properties = data.get("properties", [])
        if not properties:
            return _estimated_hotel(destination)

        check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
        check_out_dt = datetime.strptime(check_out, "%Y-%m-%d")
        nights = max((check_out_dt - check_in_dt).days, 1)

        under_budget = [p for p in properties if p.get("rate_per_night", {}).get("lowest", 9999) <= budget_ceiling_usd]
        over_budget = False
        if under_budget:
            pick = min(under_budget, key=lambda p: p.get("rate_per_night", {}).get("lowest", 9999))
        else:
            pick = min(properties, key=lambda p: p.get("rate_per_night", {}).get("lowest", 9999))
            over_budget = True

        price_per_night = float(pick.get("rate_per_night", {}).get("lowest", 120.0))
        name = pick.get("name", "Unknown Hotel")
        if over_budget:
            name += " (over budget)"

        result = HotelResult(
            name=name,
            address=pick.get("description", destination),
            price_per_night_usd=price_per_night,
            total_price_usd=round(price_per_night * nights, 2),
            rating=float(pick.get("overall_rating", 0.0)),
            is_estimated=False,
        )

        try:
            doc = {**result, "key": cache_key, "cached_at": datetime.now(timezone.utc)}
            await collection.update_one({"key": cache_key}, {"$set": doc}, upsert=True)
        except Exception as write_exc:  # noqa: BLE001
            logger.warning("Hotel cache write failed: %s", write_exc)
        return result

    except Exception as exc:  # noqa: BLE001
        logger.error("search_hotels error: %s", exc)
        return _estimated_hotel(destination)


if __name__ == "__main__":
    import asyncio

    async def _test() -> None:
        flight = await search_flights("JFK", "LAX", "2025-06-01", "2025-06-07")
        print("Flight:", flight)
        hotel = await search_hotels("Los Angeles", "2025-06-01", "2025-06-07", 200.0)
        print("Hotel:", hotel)

    asyncio.run(_test())
