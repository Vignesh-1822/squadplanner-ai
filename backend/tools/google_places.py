"""Google Places (New) — fetch activities by category near a destination."""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from agent.state import ActivityResult
from config import settings
from db.client import get_collection

logger = logging.getLogger(__name__)

_CACHE_TTL_HOURS = 24

CATEGORY_TYPE_MAP: dict[str, str] = {
    "outdoor": "park",
    "food": "restaurant",
    "nightlife": "bar",
    "urban": "tourist_attraction",
    "shopping": "shopping_mall",
}

_PRICE_LEVEL_MAP: dict[str, int] = {
    "FREE": 0,
    "INEXPENSIVE": 1,
    "MODERATE": 2,
    "EXPENSIVE": 3,
    "VERY_EXPENSIVE": 4,
}


async def fetch_activities_by_category(
    destination: str,
    coords: dict,
    categories: list[str],
    max_per_category: int = 10,
) -> list[ActivityResult]:
    """Return a flat list of ActivityResults for all requested categories."""
    collection = get_collection("api_cache")
    all_results: list[ActivityResult] = []

    for category in categories:
        if category not in CATEGORY_TYPE_MAP:
            logger.warning("Unknown category '%s' — skipping", category)
            continue

        cache_key = f"places:{destination}:{category}"

        # --- cache read (best-effort: Mongo down = cache miss) ---
        cached_hit = False
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=_CACHE_TTL_HOURS)
            cached = await collection.find_one({"key": cache_key, "cached_at": {"$gte": cutoff}})
            if cached:
                all_results.extend([ActivityResult(**a) for a in cached["places"]])
                cached_hit = True
        except Exception as cache_exc:  # noqa: BLE001
            logger.warning("Cache read failed for '%s' (continuing without cache): %s", category, cache_exc)

        if cached_hit:
            continue

        # --- live API call ---
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://places.googleapis.com/v1/places:searchNearby",
                    headers={
                        "X-Goog-Api-Key": settings.google_places_api_key,
                        "X-Goog-FieldMask": (
                            "places.id,places.displayName,places.formattedAddress,"
                            "places.location,places.priceLevel,places.rating,places.types"
                        ),
                    },
                    json={
                        "includedTypes": [CATEGORY_TYPE_MAP[category]],
                        "maxResultCount": max_per_category,
                        "locationRestriction": {
                            "circle": {
                                "center": {
                                    "latitude": coords["lat"],
                                    "longitude": coords["lng"],
                                },
                                "radius": 20000.0,
                            }
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            parsed: list[ActivityResult] = []
            for place in data.get("places", []):
                raw_price = place.get("priceLevel", "FREE")
                price_level = _PRICE_LEVEL_MAP.get(raw_price, 0) if isinstance(raw_price, str) else int(raw_price)
                parsed.append(
                    ActivityResult(
                        place_id=place["id"],
                        name=place["displayName"]["text"],
                        category=category,
                        address=place.get("formattedAddress", ""),
                        lat=place["location"]["latitude"],
                        lng=place["location"]["longitude"],
                        price_level=price_level,
                        rating=float(place.get("rating", 0.0)),
                        tags=place.get("types", []),
                    )
                )

            # cache write (best-effort)
            try:
                doc = {
                    "key": cache_key,
                    "places": [dict(a) for a in parsed],
                    "cached_at": datetime.now(timezone.utc),
                }
                await collection.update_one({"key": cache_key}, {"$set": doc}, upsert=True)
            except Exception as write_exc:  # noqa: BLE001
                logger.warning("Cache write failed for '%s': %s", category, write_exc)

            all_results.extend(parsed)

        except Exception as exc:  # noqa: BLE001
            logger.error("fetch_activities_by_category API error for category '%s': %s", category, exc)

    return all_results


async def find_place_by_text(
    query: str,
    destination: str,
    coords: dict | None = None,
    included_type: str | None = None,
) -> ActivityResult | None:
    """Find one place by text and return coordinates in the ActivityResult shape."""
    clean_query = " ".join(str(query or "").split())
    if not clean_query:
        return None

    collection = get_collection("api_cache")
    type_part = included_type or "any"
    cache_key = f"places_text:{destination}:{type_part}:{clean_query}".lower()

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=_CACHE_TTL_HOURS)
        cached = await collection.find_one({"key": cache_key, "cached_at": {"$gte": cutoff}})
        if cached and cached.get("place"):
            place = dict(cached["place"])
            return ActivityResult(**place)
    except Exception as cache_exc:  # noqa: BLE001
        logger.warning("Place text cache read failed for '%s': %s", clean_query, cache_exc)

    request_body: dict = {
        "textQuery": f"{clean_query}, {destination}",
        "maxResultCount": 1,
    }
    if included_type:
        request_body["includedType"] = included_type
    if coords and coords.get("lat") is not None and coords.get("lng") is not None:
        request_body["locationBias"] = {
            "circle": {
                "center": {
                    "latitude": float(coords["lat"]),
                    "longitude": float(coords["lng"]),
                },
                "radius": 30000.0,
            }
        }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers={
                    "X-Goog-Api-Key": settings.google_places_api_key,
                    "X-Goog-FieldMask": (
                        "places.id,places.displayName,places.formattedAddress,"
                        "places.location,places.priceLevel,places.rating,places.types"
                    ),
                },
                json=request_body,
            )
            resp.raise_for_status()
            data = resp.json()

        places = data.get("places", [])
        if not places:
            return None

        place = places[0]
        raw_price = place.get("priceLevel", "FREE")
        price_level = _PRICE_LEVEL_MAP.get(raw_price, 0) if isinstance(raw_price, str) else int(raw_price)
        parsed = ActivityResult(
            place_id=place["id"],
            name=place["displayName"]["text"],
            category="food" if included_type == "restaurant" else "place",
            address=place.get("formattedAddress", ""),
            lat=place["location"]["latitude"],
            lng=place["location"]["longitude"],
            price_level=price_level,
            rating=float(place.get("rating", 0.0)),
            tags=place.get("types", []),
        )

        try:
            doc = {
                "key": cache_key,
                "place": dict(parsed),
                "cached_at": datetime.now(timezone.utc),
            }
            await collection.update_one({"key": cache_key}, {"$set": doc}, upsert=True)
        except Exception as write_exc:  # noqa: BLE001
            logger.warning("Place text cache write failed for '%s': %s", clean_query, write_exc)

        return parsed
    except Exception as exc:  # noqa: BLE001
        logger.error("find_place_by_text API error for '%s': %s", clean_query, exc)
        return None


if __name__ == "__main__":
    import asyncio

    async def _test() -> None:
        results = await fetch_activities_by_category(
            destination="New York City",
            coords={"lat": 40.7128, "lng": -74.006},
            categories=["urban", "food"],
            max_per_category=5,
        )
        for r in results:
            print(r["name"], r["category"], r["rating"])

    asyncio.run(_test())
