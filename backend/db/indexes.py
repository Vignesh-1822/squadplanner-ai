"""MongoDB index declarations and startup data migrations."""

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING

from db.client import get_database
from tools.google_places import _CACHE_TTL_HOURS as GOOGLE_PLACES_CACHE_TTL_HOURS
from tools.serpapi import _CACHE_TTL_HOURS as SERPAPI_CACHE_TTL_HOURS

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = max(
    GOOGLE_PLACES_CACHE_TTL_HOURS,
    SERPAPI_CACHE_TTL_HOURS,
) * 60 * 60

INDEX_SPECS: list[dict[str, Any]] = [
    {"collection": "trips", "keys": [("trip_id", ASCENDING)], "options": {"unique": True}},
    {"collection": "trips", "keys": [("invite_code", ASCENDING)], "options": {"unique": True}},
    {"collection": "trips", "keys": [("created_by", ASCENDING)], "options": {}},
    {"collection": "trips", "keys": [("invited_members.email", ASCENDING)], "options": {}},
    {"collection": "users", "keys": [("email", ASCENDING)], "options": {"unique": True}},
    {"collection": "api_cache", "keys": [("key", ASCENDING)], "options": {}},
    {
        "collection": "api_cache",
        "keys": [("cached_at", ASCENDING)],
        "options": {"expireAfterSeconds": CACHE_TTL_SECONDS},
    },
    {
        "collection": "api_usage",
        "keys": [("type", ASCENDING), ("month", ASCENDING)],
        "options": {"unique": True},
    },
]


async def _migrate_serpapi_usage() -> None:
    """Move the current month's legacy counter without lowering an existing value."""
    db = get_database()
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    legacy_filter = {"type": "serpapi_usage", "month": current_month}
    legacy_doc = await db["api_cache"].find_one(legacy_filter)
    if not legacy_doc:
        return

    calls_used = int(legacy_doc.get("calls_used", 0))
    await db["api_usage"].update_one(
        legacy_filter,
        {"$max": {"calls_used": calls_used}},
        upsert=True,
    )
    await db["api_cache"].delete_one(legacy_filter)
    logger.info("Migrated the %s SerpAPI usage counter to api_usage.", current_month)


async def ensure_indexes() -> None:
    """Create required indexes and perform idempotent startup migrations."""
    db = get_database()
    for spec in INDEX_SPECS:
        await db[spec["collection"]].create_index(
            spec["keys"],
            **spec["options"],
        )

    await _migrate_serpapi_usage()

    users = db["users"]
    if "google_id_1" in await users.index_information():
        await users.drop_index("google_id_1")
        logger.info("Dropped unused users.google_id_1 index.")
