"""Database index declarations and migration tests without MongoDB."""

import pytest

from db import indexes


def test_index_specs_cover_phase_zero_requirements():
    declared = {
        (
            spec["collection"],
            tuple(spec["keys"]),
            tuple(sorted(spec["options"].items())),
        )
        for spec in indexes.INDEX_SPECS
    }
    assert declared == {
        ("trips", (("trip_id", 1),), (("unique", True),)),
        ("trips", (("invite_code", 1),), (("unique", True),)),
        ("trips", (("created_by", 1),), ()),
        ("trips", (("invited_members.email", 1),), ()),
        ("users", (("email", 1),), (("unique", True),)),
        ("api_cache", (("key", 1),), ()),
        ("api_cache", (("cached_at", 1),), (("expireAfterSeconds", 86400),)),
        ("api_usage", (("type", 1), ("month", 1)), (("unique", True),)),
    }


class FakeCollection:
    def __init__(self, legacy=None, index_info=None):
        self.legacy = legacy
        self.index_info = index_info or {}
        self.created = []
        self.updated = []
        self.deleted = []
        self.dropped = []

    async def create_index(self, keys, **options):
        self.created.append((keys, options))

    async def find_one(self, query):
        return self.legacy

    async def update_one(self, query, update, **options):
        self.updated.append((query, update, options))

    async def delete_one(self, query):
        self.deleted.append(query)
        self.legacy = None

    async def index_information(self):
        return self.index_info

    async def drop_index(self, name):
        self.dropped.append(name)
        self.index_info.pop(name, None)


@pytest.mark.asyncio
async def test_ensure_indexes_preserves_usage_and_is_idempotent(monkeypatch):
    collections = {
        "trips": FakeCollection(),
        "users": FakeCollection(index_info={"google_id_1": {}}),
        "api_cache": FakeCollection(legacy={"calls_used": 17}),
        "api_usage": FakeCollection(),
    }
    monkeypatch.setattr(indexes, "get_database", lambda: collections)

    await indexes.ensure_indexes()
    await indexes.ensure_indexes()

    usage_updates = collections["api_usage"].updated
    assert len(usage_updates) == 1
    assert usage_updates[0][1] == {"$max": {"calls_used": 17}}
    assert usage_updates[0][2] == {"upsert": True}
    assert len(collections["api_cache"].deleted) == 1
    assert collections["users"].dropped == ["google_id_1"]
