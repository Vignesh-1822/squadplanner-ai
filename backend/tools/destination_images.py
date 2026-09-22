"""Destination photography — Wikipedia first, Unsplash as fallback, cached in Mongo.

Why not Google Places, which has the best coverage: under the Maps Platform terms photos have
no caching exception at all — neither the bytes nor the photo name may be stored, and the name
expires. Every render would be another billable call. That rules out sharing one lookup across
every squad who sees the destination, which is the whole point here.

Wikipedia is keyed to the *named place*, so it returns a photo of the actual location rather
than something generic that merely matches a search term, and Commons content is CC-licensed
for commercial reuse with attribution — so it may be cached. Unsplash covers the gaps; its
guidelines require hotlinking their CDN, so we cache the URL and never the image itself.

The 480 destinations are a fixed shared set, so the cache warms quickly: a destination resolves
once and every later squad that sees it gets the cached answer.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from config import settings
from db.client import get_collection

logger = logging.getLogger(__name__)

# Deliberately NOT the shared ``api_cache`` collection: that carries a collection-wide TTL
# index (cached_at, 86400s) for the Places and SerpAPI caches, which must expire. A resolved
# destination photo is stable derived data — expiring it daily would re-resolve all 480 every
# day, for nothing, and get us rate-limited by Wikimedia.
_COLLECTION = "destination_images"

_WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_UNSPLASH_SEARCH = "https://api.unsplash.com/search/photos"

# Wikimedia's robot policy rejects requests whose User-Agent carries no way to contact the
# operator — a generic string or a browser-like one gets a flat 403. A project URL is enough.
_USER_AGENT = f"SquadPlannerAI/0.1 ({settings.wikimedia_contact})"

# Wikipedia titles places with the full state name ("Albuquerque, New Mexico"), while the
# dataset stores postal abbreviations, so they have to be expanded before lookup.
_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "Washington, D.C.",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}

# Images of real places don't change, so a resolved hit is kept indefinitely. Misses are
# re-checked after a while in case an article gains a photo.
_MISS_RECHECK_DAYS = 30


# Manually sourced photos, for the handful of places Wikipedia has no image for.
# See data/destination_images/README.md.
_MANUAL_DIR = Path(__file__).resolve().parent.parent / "data" / "destination_images"
_MANUAL_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
_CREDITS_FILE = "_credits.json"


def _cache_key(destination_id: str) -> str:
    return f"destination_image:{destination_id}"


def _manual_credits() -> dict[str, Any]:
    path = _MANUAL_DIR / _CREDITS_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read %s: %s", path, exc)
        return {}


def _manual_image(destination_id: str) -> dict[str, Any] | None:
    """A photo added by hand wins over anything we could look up.

    Two forms. A file dropped in as ``<destination id><ext>`` is served by this API — a copy
    with no config to edit, and the normal case. A ``url`` in ``_credits.json`` is honoured
    instead for sources that forbid rehosting: Unsplash's guidelines require their CDN to be
    hotlinked, so those images stay remote.
    """
    credit = _manual_credits().get(destination_id, {})

    for extension in _MANUAL_EXTENSIONS:
        path = _MANUAL_DIR / f"{destination_id}{extension}"
        if path.exists():
            return {
                "image_url": f"{settings.public_base_url.rstrip('/')}/static/destination-images/{path.name}",
                "image_source": credit.get("source", "manual"),
                "image_credit": credit.get("credit", ""),
                "image_link": credit.get("link", ""),
            }

    if credit.get("url"):
        return {
            "image_url": credit["url"],
            "image_source": credit.get("source", "manual"),
            "image_credit": credit.get("credit", ""),
            "image_link": credit.get("link", ""),
        }
    return None


def _wiki_titles(name: str, state: str) -> list[str]:
    """Candidate article titles, most specific first.

    "Springfield" is ambiguous; "Springfield, Illinois" is not — so the state-qualified title is
    tried first. National parks and named regions have no state suffix, hence the bare fallback.
    """
    titles = []
    full_state = _STATES.get(state.upper()) if state else None
    if full_state:
        titles.append(f"{name}, {full_state}")
    if state and state != full_state:
        titles.append(f"{name}, {state}")
    titles.append(name)
    return list(dict.fromkeys(titles))


async def _wiki_get(client: httpx.AsyncClient, title: str) -> httpx.Response | None:
    """GET one article summary, backing off when Wikimedia throttles us.

    A trip only resolves five destinations, so this rarely matters in production — but a bulk
    warm-up of the whole dataset gets throttled without it, and a 429 silently reads as "no
    image exists", which is a far worse failure than being slow.
    """
    url = _WIKI_SUMMARY.format(title=quote(title.replace(" ", "_"), safe=""))
    for attempt in range(3):
        resp = await client.get(url, headers={"User-Agent": _USER_AGENT})
        if resp.status_code in (403, 429):
            await asyncio.sleep(1.5 * (attempt + 1))
            continue
        return resp
    return None


async def _from_wikipedia(client: httpx.AsyncClient, name: str, state: str) -> dict[str, Any] | None:
    for title in _wiki_titles(name, state):
        try:
            resp = await _wiki_get(client, title)
            if resp is None or resp.status_code != 200:
                continue
            data = resp.json()
            # A disambiguation page means the title is shared (Glacier National Park exists in
            # both the US and Canada); the country-qualified article is the one we want.
            if data.get("type") == "disambiguation":
                qualified = await _wiki_get(client, f"{name} (U.S.)")
                if qualified is not None and qualified.status_code == 200:
                    data = qualified.json()
                else:
                    continue
            image = (data.get("originalimage") or {}).get("source") or (
                data.get("thumbnail") or {}
            ).get("source")
            if image:
                return {
                    "image_url": image,
                    "image_source": "wikipedia",
                    "image_credit": data.get("title", title),
                    "image_link": (data.get("content_urls", {}).get("desktop", {}) or {}).get("page", ""),
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Wikipedia lookup failed for '%s': %s", title, exc)
    return None


async def _from_unsplash(client: httpx.AsyncClient, name: str, state: str) -> dict[str, Any] | None:
    if not settings.unsplash_access_key:
        return None
    try:
        resp = await client.get(
            _UNSPLASH_SEARCH,
            params={"query": f"{name} {state}".strip(), "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {settings.unsplash_access_key}"},
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        if not results:
            return None
        photo = results[0]
        user = photo.get("user", {}) or {}
        return {
            # Unsplash requires hotlinking their CDN, so this URL is stored and never the file.
            "image_url": (photo.get("urls") or {}).get("regular", ""),
            "image_source": "unsplash",
            "image_credit": user.get("name", "Unsplash"),
            "image_link": (user.get("links") or {}).get("html", ""),
            # Their guidelines require pinging this whenever the photo is used.
            "image_download_location": (photo.get("links") or {}).get("download_location", ""),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unsplash lookup failed for '%s': %s", name, exc)
        return None


async def resolve_destination_image(
    destination_id: str,
    name: str,
    state: str = "",
    *,
    use_cache: bool = True,
) -> dict[str, Any] | None:
    """Return image metadata for one destination, or None when nothing resolves."""
    # Checked before the cache: a photo added by hand is an explicit override, and must win
    # even when an automatic lookup already cached something for this destination.
    manual = _manual_image(destination_id)
    if manual:
        return manual

    collection = get_collection(_COLLECTION)
    key = _cache_key(destination_id)

    if use_cache:
        try:
            cached = await collection.find_one({"key": key})
            if cached and cached.get("image_url"):
                return {k: v for k, v in cached.items() if k.startswith("image_")}
            if cached and not cached.get("image_url"):
                age = datetime.now(timezone.utc) - cached["cached_at"].replace(tzinfo=timezone.utc)
                if age.days < _MISS_RECHECK_DAYS:
                    return None  # known miss, still fresh
        except Exception as exc:  # noqa: BLE001
            logger.warning("Image cache read failed for '%s': %s", destination_id, exc)

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        found = await _from_wikipedia(client, name, state)
        if not found:
            found = await _from_unsplash(client, name, state)

    try:
        await collection.update_one(
            {"key": key},
            {"$set": {"key": key, "cached_at": datetime.now(timezone.utc), **(found or {"image_url": ""})}},
            upsert=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Image cache write failed for '%s': %s", destination_id, exc)

    return found


async def attach_images(candidates: list[dict]) -> list[dict]:
    """Resolve images for a candidate shortlist concurrently, in place."""
    results = await asyncio.gather(
        *(
            resolve_destination_image(c.get("id", ""), c.get("name", ""), c.get("state", ""))
            for c in candidates
        ),
        return_exceptions=True,
    )
    for candidate, result in zip(candidates, results):
        if isinstance(result, dict):
            candidate.update(result)
    return candidates
