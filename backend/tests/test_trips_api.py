from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import squad as squad_api
from api import trips as trips_api


class _AsyncCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._docs:
            raise StopAsyncIteration
        return self._docs.pop(0)


class FakeCollection:
    """Stands in for both the trips and users collections."""

    def __init__(self, trip=None, users=None):
        self.trip = trip
        self.users = users or []
        self.inserted = None
        self.updated = None

    async def find_one(self, query, projection=None):
        return self.trip if query.get("trip_id") == self.trip.get("trip_id") else None

    def find(self, query=None, projection=None):
        return _AsyncCursor(self.users)

    async def insert_one(self, document):
        self.inserted = document

    async def update_one(self, query, update):
        self.updated = {"query": query, "update": update}


def _trip(**overrides):
    trip = {
        "trip_id": "trip-1",
        "trip_name": "Chicago Weekend",
        "invite_code": "abc123",
        "status": "collecting",
        "created_by": "leader@example.com",
        "created_at": datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        "invited_members": [
            {"email": "leader@example.com", "status": "ready", "is_leader": True,
             "preferences": {"origin_city": "ORD"}},
            {"email": "guest@example.com", "status": "pending", "is_leader": False},
        ],
        "initial_state": {"internal": True},
    }
    trip.update(overrides)
    return trip


@pytest.mark.asyncio
async def test_get_trip_returns_lobby_shape(monkeypatch):
    collection = FakeCollection(_trip())
    monkeypatch.setattr(trips_api, "get_collection", lambda name: collection)

    response = await trips_api.get_trip("trip-1")

    assert response == {
        "trip_id": "trip-1",
        "trip_name": "Chicago Weekend",
        "invite_code": "abc123",
        "status": "collecting",
        "created_at": "2026-06-16T12:00:00+00:00",
        "expires_at": "2026-06-17T12:00:00+00:00",
        "invited_members": [
            {"email": "leader@example.com", "status": "ready", "name": "Leader",
             "avatar_url": "", "is_leader": True, "has_preferences": True},
            {"email": "guest@example.com", "status": "pending", "name": "Guest",
             "avatar_url": "", "is_leader": False, "has_preferences": False},
        ],
        "ready_count": 1,
        "total_count": 2,
        "all_ready": False,
        "can_generate": False,
    }


@pytest.mark.asyncio
async def test_can_generate_requires_every_member_ready(monkeypatch):
    """The strict gate: the leader being ready is not enough."""
    members = [
        {"email": "leader@example.com", "status": "ready", "is_leader": True,
         "preferences": {"origin_city": "ORD"}},
        {"email": "guest@example.com", "status": "ready", "is_leader": False,
         "preferences": {"origin_city": "ATL"}},
    ]
    collection = FakeCollection(_trip(invited_members=members))
    monkeypatch.setattr(trips_api, "get_collection", lambda name: collection)

    response = await trips_api.get_trip("trip-1")

    assert response["all_ready"] is True
    assert response["can_generate"] is True
    assert response["ready_count"] == response["total_count"] == 2


@pytest.mark.asyncio
async def test_can_generate_is_false_once_planning_started(monkeypatch):
    members = [
        {"email": "leader@example.com", "status": "ready", "is_leader": True,
         "preferences": {"origin_city": "ORD"}},
    ]
    collection = FakeCollection(_trip(invited_members=members, status="generating"))
    monkeypatch.setattr(trips_api, "get_collection", lambda name: collection)

    response = await trips_api.get_trip("trip-1")

    assert response["all_ready"] is True
    assert response["can_generate"] is False


@pytest.mark.asyncio
async def test_get_trip_uses_one_user_query_for_the_whole_squad(monkeypatch):
    """The lobby polls this route, so member enrichment must not be N+1."""
    collection = FakeCollection(_trip())
    calls = {"find": 0}
    original_find = collection.find

    def counting_find(*args, **kwargs):
        calls["find"] += 1
        return original_find(*args, **kwargs)

    collection.find = counting_find
    monkeypatch.setattr(trips_api, "get_collection", lambda name: collection)

    await trips_api.get_trip("trip-1")

    assert calls["find"] == 1


@pytest.mark.asyncio
async def test_get_trip_backfills_invited_members_from_legacy_emails(monkeypatch):
    trip = {
        "trip_id": "trip-2",
        "trip_name": "Austin Weekend",
        "invite_code": "xyz789",
        "status": "pending",
        "created_at": "2026-06-16T12:00:00+00:00",
        "invited_emails": ["a@example.com", "b@example.com"],
    }
    collection = FakeCollection(trip)
    monkeypatch.setattr(trips_api, "get_collection", lambda name: collection)

    response = await trips_api.get_trip("trip-2")

    assert [m["email"] for m in response["invited_members"]] == [
        "a@example.com",
        "b@example.com",
    ]
    assert all(m["status"] == "pending" for m in response["invited_members"])
    assert collection.updated["query"] == {"trip_id": "trip-2"}


@pytest.mark.asyncio
async def test_get_trip_heals_a_legacy_trip_missing_its_leader(monkeypatch):
    """Trips created before the creator became a squad member have no leader entry."""
    trip = _trip(invited_members=[{"email": "guest@example.com", "status": "pending"}])
    collection = FakeCollection(trip)
    monkeypatch.setattr(trips_api, "get_collection", lambda name: collection)

    response = await trips_api.get_trip("trip-1")

    assert [(m["email"], m["is_leader"]) for m in response["invited_members"]] == [
        ("leader@example.com", True),
        ("guest@example.com", False),
    ]
    assert response["total_count"] == 2
    # The repair is persisted, or generation would still fail for want of a leader.
    assert collection.updated["update"]["$set"]["invited_members"][0] == {
        "email": "leader@example.com",
        "status": "joined",
        "is_leader": True,
    }


@pytest.mark.asyncio
async def test_create_trip_makes_the_creator_the_leader(monkeypatch):
    collection = FakeCollection({"trip_id": "unused"})
    monkeypatch.setattr(trips_api, "get_collection", lambda name: collection)

    async def send_trip_invite(*args, **kwargs):
        return None

    monkeypatch.setattr(trips_api, "send_trip_invite", send_trip_invite)

    await trips_api.create_trip(
        trips_api.CreateTripRequest(
            trip_name="Denver Weekend",
            created_by="leader@example.com",
            invited_emails=["a@example.com", "b@example.com"],
        )
    )

    assert collection.inserted["invited_members"] == [
        {"email": "leader@example.com", "status": "joined", "is_leader": True},
        {"email": "a@example.com", "status": "pending", "is_leader": False},
        {"email": "b@example.com", "status": "pending", "is_leader": False},
    ]


@pytest.mark.asyncio
async def test_remove_member_drops_a_straggler(monkeypatch):
    collection = FakeCollection(_trip())
    monkeypatch.setattr(squad_api, "get_collection", lambda name: collection)

    result = await squad_api.remove_member(
        "trip-1", "guest@example.com", current_user={"email": "leader@example.com"}
    )

    assert result["removed"] == "guest@example.com"
    assert [m["email"] for m in result["invited_members"]] == ["leader@example.com"]
    assert collection.updated["update"]["$pull"] == {"invited_emails": "guest@example.com"}


@pytest.mark.asyncio
async def test_remove_member_is_leader_only(monkeypatch):
    collection = FakeCollection(_trip())
    monkeypatch.setattr(squad_api, "get_collection", lambda name: collection)

    with pytest.raises(HTTPException) as exc:
        await squad_api.remove_member(
            "trip-1", "leader@example.com", current_user={"email": "guest@example.com"}
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_remove_member_refuses_to_remove_the_leader(monkeypatch):
    collection = FakeCollection(_trip())
    monkeypatch.setattr(squad_api, "get_collection", lambda name: collection)

    with pytest.raises(HTTPException) as exc:
        await squad_api.remove_member(
            "trip-1", "leader@example.com", current_user={"email": "leader@example.com"}
        )

    assert exc.value.status_code == 422
