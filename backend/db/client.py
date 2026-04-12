"""Motor async MongoDB client singleton."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_database() -> AsyncIOMotorDatabase:
    """Return the `squadplanner` database, creating the client on first use."""
    global _client, _db
    if _db is not None:
        return _db
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _client["squadplanner"]
    return _db


def get_collection(name: str) -> AsyncIOMotorCollection:
    """Return a collection on the default database."""
    return get_database()[name]


def close_client() -> None:
    """Close the MongoDB client if it was opened."""
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
