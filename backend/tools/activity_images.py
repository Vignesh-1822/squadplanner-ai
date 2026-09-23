"""Photography for individual itinerary stops.

Destinations resolve from Wikipedia (see tools/destination_images.py), but that only works for
places with an article — "Golden Gate Bridge" has one, "Ichiran Ramen Shibuya" does not. So this
layers two sources:

  1. **Wikipedia** for landmarks. Free, unlimited, and the article is unambiguously about the
     place, so nothing has to be verified.
  2. **SerpAPI Google Images** for everything else — restaurants, bars, shops. Metered, so it is
     tried second and gated by the same monthly budget as flights and hotels.

Results are cached by Google `place_id`, which is stable and already stored on every activity.
The cache is what makes this affordable: venues recur across trips, so a busy destination
resolves once and is free thereafter. It lives in its own collection rather than `api_cache`,
which carries a 24h TTL index that would throw the work away nightly.

A note on the images themselves: Google Images results are hotlinks to third-party sites, so the
underlying photographs belong to whoever published them. The gstatic thumbnail is Google's own
cached copy and is what gets stored here. That is the pragmatic choice for a demo; a commercial
deployment should license its imagery properly.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from config import settings
from db.client import get_collection
from tools.destination_images import _USER_AGENT, _WIKI_SUMMARY, _wiki_get
from tools.serpapi import SerpAPILimitReached, check_and_increment_serpapi_budget

logger = logging.getLogger(__name__)

_COLLECTION = "activity_images"
_SERPAPI_IMAGES = "https://serpapi.com/search.json"

# Misses are re-checked eventually in case a venue gains coverage, but not often — each retry
# can cost a metered search.
_MISS_RECHECK_DAYS = 45


def _cache_key(place_id: str) -> str:
    return f"activity_image:{place_id}"


def _venue_key(name: str, destination: str) -> str:
    """Cache key for a venue with no place_id — meals arrive as bare strings."""
    slug = re.sub(r"[^a-z0-9]+", "_", f"{name} {destination}".lower()).strip("_")
    return f"venue_image:{slug}"


def meal_venue(meal: str) -> str:
    """"Dinner at Tartine Manufactory" -> "Tartine Manufactory"."""
    parts = re.split(r"\s+at\s+", meal, maxsplit=1)
    return parts[1].strip() if len(parts) == 2 else ""


_WIKI_ACTION = "https://en.wikipedia.org/w/api.php"
_TARGET_WIDTH = 800


async def _from_wikipedia(client: httpx.AsyncClient, name: str) -> dict[str, Any] | None:
    """Ask Wikipedia for a card-sized image of this place.

    Uses the `pageimages` action API with `pithumbsize` so MediaWiki *generates* the rendition
    and hands back a URL that exists. Rewriting the width in a thumbnail URL by hand does not
    work: Wikimedia serves only the widths it has generated and answers 400 for anything else —
    330px and 3840px resolve for a given file while 640, 800 and 1024 all fail.

    Only landmarks will hit; a restaurant name simply misses, which costs nothing.
    """
    try:
        resp = await client.get(
            _WIKI_ACTION,
            params={
                "action": "query",
                "format": "json",
                "prop": "pageimages|pageprops",
                "piprop": "thumbnail",
                "pithumbsize": _TARGET_WIDTH,
                "titles": name,
                "redirects": 1,
            },
        )
        if resp.status_code != 200:
            return None

        pages = (resp.json().get("query") or {}).get("pages") or {}
        for page in pages.values():
            if "missing" in page:
                continue
            # A disambiguation page's image describes nothing in particular.
            if "disambiguation" in (page.get("pageprops") or {}):
                continue
            source = (page.get("thumbnail") or {}).get("source")
            if source:
                return {
                    "image_url": source,
                    "image_source": "wikipedia",
                    "image_credit": page.get("title", name),
                }
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Wikipedia activity lookup failed for %s: %s", name, exc)
        return None


async def _from_serpapi(client: httpx.AsyncClient, query: str) -> dict[str, Any] | None:
    if not settings.serpapi_key:
        return None
    try:
        await check_and_increment_serpapi_budget()
    except SerpAPILimitReached:
        logger.warning("SerpAPI budget spent; skipping image lookup for %s", query)
        return None

    try:
        resp = await client.get(
            _SERPAPI_IMAGES,
            params={
                "engine": "google_images",
                "q": query,
                "api_key": settings.serpapi_key,
                "num": 5,
            },
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("images_results") or []
        if not results:
            return None
        top = results[0]
        # Prefer the full-resolution original: the gstatic thumbnail is only ~150px and looks
        # soft at card size. It stays as the fallback when no original is offered.
        url = top.get("original") or top.get("thumbnail")
        if not url:
            return None
        return {
            "image_url": url,
            "image_source": "google_images",
            "image_credit": top.get("source", ""),
            "image_link": top.get("link", ""),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("SerpAPI image lookup failed for %s: %s", query, exc)
        return None


async def resolve_activity_image(
    place_id: str, name: str, destination: str = ""
) -> dict[str, Any] | None:
    """Return image metadata for one venue, or None.

    Keyed by `place_id` where there is one; meals have none, so they fall back to a slug of the
    venue name and destination, which is stable enough to stop the same restaurant being looked
    up once per day of the trip.
    """
    if not name:
        return None

    collection = get_collection(_COLLECTION)
    key = _cache_key(place_id) if place_id else _venue_key(name, destination)

    try:
        cached = await collection.find_one({"key": key})
        if cached and cached.get("image_url"):
            return {k: v for k, v in cached.items() if k.startswith("image_")}
        if cached:
            age = datetime.now(timezone.utc) - cached["cached_at"].replace(tzinfo=timezone.utc)
            if age.days < _MISS_RECHECK_DAYS:
                return None  # known miss, and re-checking costs a metered search
    except Exception as exc:  # noqa: BLE001
        logger.warning("Activity image cache read failed for %s: %s", place_id, exc)

    async with httpx.AsyncClient(timeout=25, follow_redirects=True,
                                 headers={"User-Agent": _USER_AGENT}) as client:
        found = await _from_wikipedia(client, name)
        if not found:
            found = await _from_serpapi(client, f"{name} {destination}".strip())

    try:
        await collection.update_one(
            {"key": key},
            {"$set": {"key": key, "cached_at": datetime.now(timezone.utc),
                      **(found or {"image_url": ""})}},
            upsert=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Activity image cache write failed for %s: %s", place_id, exc)

    return found


async def attach_item_images(days: list[dict], destination: str = "") -> list[dict]:
    """Resolve photography for every stop across a trip's days.

    Works off the unified `items` list, so meals and activities take the same path — a meal stop
    carries a real `place_id` from the restaurant lookup, which is a far better cache key than
    the venue name it used to be matched on. The same venue repeats across days (one hotel
    breakfast every morning), so lookups are deduplicated before anything is fetched.
    """
    wanted: dict[str, tuple[str, str]] = {}
    for day in days or []:
        for item in day.get("items") or []:
            place = item.get("place") or {}
            name = place.get("name") or item.get("label")
            if not name:
                continue
            key = str(place.get("place_id") or "") or f"name:{name.lower()}"
            wanted.setdefault(key, (str(place.get("place_id") or ""), name))

    if not wanted:
        return days

    keys = list(wanted)
    results = await asyncio.gather(
        *(resolve_activity_image(wanted[k][0], wanted[k][1], destination) for k in keys),
        return_exceptions=True,
    )
    by_key = {k: r for k, r in zip(keys, results) if isinstance(r, dict)}

    for day in days or []:
        for item in day.get("items") or []:
            place = item.get("place") or {}
            name = place.get("name") or item.get("label")
            if not name:
                continue
            key = str(place.get("place_id") or "") or f"name:{name.lower()}"
            found = by_key.get(key)
            if found:
                item["image"] = found

    return days


async def attach_activity_images(days: list[dict], destination: str = "") -> list[dict]:
    """Legacy path for trips with no `items` (generated before route_stops existed)."""
    activities = [
        activity
        for day in days or []
        for activity in (day.get("activities") or [])
        if activity.get("place_id")
    ]
    if not activities:
        return days

    results = await asyncio.gather(
        *(
            resolve_activity_image(a["place_id"], a.get("name", ""), destination)
            for a in activities
        ),
        return_exceptions=True,
    )
    for activity, result in zip(activities, results):
        if isinstance(result, dict):
            activity.update(result)
    return days


async def attach_meal_images(days: list[dict], destination: str = "") -> list[dict]:
    """Legacy path: meals as prose, with no place_id to key on."""
    wanted: dict[str, str] = {}
    for day in days or []:
        for meal in day.get("meals") or []:
            venue = meal_venue(meal)
            if venue:
                wanted.setdefault(venue, meal)

    if not wanted:
        return days

    venues = list(wanted)
    results = await asyncio.gather(
        *(resolve_activity_image("", venue, destination) for venue in venues),
        return_exceptions=True,
    )
    by_venue = {v: r for v, r in zip(venues, results) if isinstance(r, dict)}

    for day in days or []:
        images = {}
        for meal in day.get("meals") or []:
            found = by_venue.get(meal_venue(meal))
            if found:
                images[meal] = found
        if images:
            day["meal_images"] = images

    return days
