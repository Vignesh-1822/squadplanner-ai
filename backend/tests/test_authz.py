"""Phase 0 authentication and authorization regression gate."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from api.middleware.auth import get_current_user
from api.middleware.authz import get_trips_collection, get_users_collection
from api.middleware.rate_limit import limiter
from services.auth_service import create_jwt

from main import app

TRIP_ID = "00000000-0000-0000-0000-000000000001"
REFINEMENT_ID = "00000000-0000-0000-0000-000000000002"

PUBLIC_ROUTES = frozenset(
    {
        ("GET", "/health"),
        ("GET", "/docs"),
        ("GET", "/docs/oauth2-redirect"),
        ("GET", "/redoc"),
        ("GET", "/openapi.json"),
        ("GET", "/debug"),
        ("GET", "/debug/"),
        ("POST", "/api/auth/register"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/google"),
        ("GET", "/api/trips/by-invite/{invite_code}"),
    }
)

LEADER = {"email": "leader@example.com", "token_version": 0, "is_admin": False}
MEMBER = {"email": "member@example.com", "token_version": 0, "is_admin": False}
OUTSIDER = {"email": "outsider@example.com", "token_version": 0, "is_admin": False}


class FakeCursor:
    def sort(self, *args):
        return self

    def skip(self, *args):
        return self

    def limit(self, *args):
        return self

    def __aiter__(self):
        async def iterate():
            if False:
                yield None

        return iterate()


class FakeTrips:
    def __init__(self, trip: dict):
        self.trip = trip
        self.inserted: dict | None = None
        self.updates: list[tuple[dict, dict]] = []

    async def find_one(self, query, projection=None):
        if query.get("trip_id") == self.trip.get("trip_id"):
            return self.trip
        if query.get("invite_code") == self.trip.get("invite_code"):
            return self.trip
        return None

    async def insert_one(self, document):
        self.inserted = document

    async def update_one(self, query, update, **kwargs):
        self.updates.append((query, update))

    def find(self, query):
        return FakeCursor()


class FakeUsers:
    async def find_one(self, query, projection=None):
        email = query.get("email", "")
        return {"email": email, "name": email.split("@")[0].capitalize(), "avatar_url": ""}


def _trip() -> dict:
    return {
        "trip_id": TRIP_ID,
        "trip_name": "Security Test",
        "invite_code": "valid-invite",
        "created_by": LEADER["email"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete",
        "initial_state": {"trip_id": TRIP_ID},
        "final_state": {"trip_pitch": "Done"},
        "trip_pitch": "Done",
        "itinerary": {"days": []},
        "invited_members": [
            {"email": LEADER["email"], "status": "ready", "is_leader": True},
            {"email": MEMBER["email"], "status": "joined", "is_leader": False},
        ],
        "refinements": {REFINEMENT_ID: {"status": "queued"}},
    }


def _override_user(user):
    async def dependency():
        return user

    return dependency


@pytest.fixture(autouse=True)
def clean_dependencies():
    limiter.reset()
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    limiter.reset()


def _iter_app_routes():
    """Enumerate the live table, including FastAPI's lazy included routers."""
    for route in app.routes:
        if type(route).__name__ == "_IncludedRouter":
            prefix = route.include_context.prefix
            for child in route.original_router.routes:
                if isinstance(child, APIRoute):
                    for method in child.methods:
                        if method not in {"HEAD", "OPTIONS"}:
                            yield method, f"{prefix}{child.path}"
        elif isinstance(route, APIRoute):
            for method in route.methods:
                if method not in {"HEAD", "OPTIONS"}:
                    yield method, route.path
        elif type(route).__name__ == "Mount" and route.path == "/debug":
            yield "GET", "/debug"
            yield "GET", "/debug/"
        elif getattr(route, "methods", None):
            for method in route.methods:
                if method not in {"HEAD", "OPTIONS"}:
                    yield method, route.path


def _request_path(path: str) -> str:
    return (
        path.replace("{trip_id}", TRIP_ID)
        .replace("{refinement_id}", REFINEMENT_ID)
        .replace("{invite_code}", "dummy-invite")
    )


def _request_body(path: str) -> dict:
    if path == "/api/trips":
        return {"trip_name": "Anonymous"}
    if path.endswith("/join"):
        return {"invite_code": "dummy-invite"}
    if path.endswith("/preferences"):
        return {"origin_city": "ORD", "budget_usd": 1000}
    if path.endswith("/confirm-city"):
        return {"selected_destination": "Chicago", "selected_destination_coords": {"lat": 1, "lng": 1}}
    if path.endswith("/refine"):
        return {"message": "Make Day 2 cheaper"}
    return {}


def test_public_route_allow_list_is_explicit():
    assert PUBLIC_ROUTES == {
        ("GET", "/health"),
        ("GET", "/docs"),
        ("GET", "/docs/oauth2-redirect"),
        ("GET", "/redoc"),
        ("GET", "/openapi.json"),
        # The static shell contains no data and must be public so users can log in from it.
        ("GET", "/debug"),
        ("GET", "/debug/"),
        ("POST", "/api/auth/register"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/google"),
        ("GET", "/api/trips/by-invite/{invite_code}"),
    }


def test_public_invite_preview_does_not_expose_email_addresses():
    trips = FakeTrips(_trip())
    app.dependency_overrides[get_trips_collection] = lambda: trips
    app.dependency_overrides[get_users_collection] = lambda: FakeUsers()

    response = TestClient(app).get("/api/trips/by-invite/valid-invite")

    assert response.status_code == 200
    assert response.json() == {
        "trip_id": TRIP_ID,
        "trip_name": "Security Test",
        "invite_code": "valid-invite",
        "member_count": 2,
        "leader_name": "Leader",
    }
    assert "@" not in response.text


def test_every_non_public_route_rejects_anonymous_callers():
    client = TestClient(app)
    discovered = set(_iter_app_routes())
    assert PUBLIC_ROUTES <= discovered

    for method, template in sorted(discovered - PUBLIC_ROUTES):
        response = client.request(
            method,
            _request_path(template),
            json=_request_body(template) if method == "POST" else None,
        )
        assert response.status_code in {401, 403}, (
            f"{method} {template} returned {response.status_code}"
        )


def test_member_and_role_matrix(monkeypatch):
    from api import hitl

    trips = FakeTrips(_trip())
    app.dependency_overrides[get_trips_collection] = lambda: trips
    app.dependency_overrides[get_users_collection] = lambda: FakeUsers()
    client = TestClient(app)

    app.dependency_overrides[get_current_user] = _override_user(OUTSIDER)
    assert client.get(f"/api/trips/{TRIP_ID}").status_code == 403

    app.dependency_overrides[get_current_user] = _override_user(MEMBER)
    assert client.get(f"/api/trips/{TRIP_ID}").status_code == 200
    assert client.post(
        f"/api/trips/{TRIP_ID}/confirm-city",
        json={"selected_destination": "Chicago", "selected_destination_coords": {"lat": 1, "lng": 1}},
    ).status_code == 403
    assert client.post(
        f"/api/trips/{TRIP_ID}/refine",
        json={"message": "Make Day 2 cheaper"},
    ).status_code == 403

    class FakeGraph:
        async def aget_state(self, config):
            return SimpleNamespace(next=("city_selection_hitl",))

    async def fake_graph():
        return FakeGraph()

    monkeypatch.setattr(hitl, "_get_orchestrator_graph", fake_graph)
    app.dependency_overrides[get_current_user] = _override_user(LEADER)
    assert client.post(
        f"/api/trips/{TRIP_ID}/confirm-city",
        json={"selected_destination": "Chicago", "selected_destination_coords": {"lat": 1, "lng": 1}},
    ).status_code != 403
    assert client.post(
        f"/api/trips/{TRIP_ID}/refine",
        json={"message": "Make Day 2 cheaper"},
    ).status_code != 403

    app.dependency_overrides[get_current_user] = _override_user(MEMBER)
    assert client.get("/api/admin/serpapi-usage").status_code == 403


def test_trip_identity_cannot_be_spoofed():
    trips = FakeTrips(_trip())
    app.dependency_overrides[get_current_user] = _override_user(LEADER)
    app.dependency_overrides[get_trips_collection] = lambda: trips

    response = TestClient(app).post(
        "/api/trips",
        json={
            "trip_name": "Owned by token",
            "created_by": "victim@example.com",
            "invited_emails": [],
        },
    )
    assert response.status_code == 200
    assert trips.inserted["created_by"] == LEADER["email"]


def test_join_code_and_preferences_membership_are_enforced():
    trips = FakeTrips(_trip())
    app.dependency_overrides[get_current_user] = _override_user(OUTSIDER)
    app.dependency_overrides[get_trips_collection] = lambda: trips
    client = TestClient(app)

    assert client.post(
        f"/api/trips/{TRIP_ID}/join",
        json={"invite_code": "wrong"},
    ).status_code == 403
    assert client.post(
        f"/api/trips/{TRIP_ID}/preferences",
        json={"origin_city": "ORD", "budget_usd": 1000},
    ).status_code == 403


def test_stale_token_version_is_rejected(monkeypatch):
    from api.middleware import auth

    class RevokedUsers:
        async def find_one(self, query, projection=None):
            return {"email": LEADER["email"], "token_version": 1}

    monkeypatch.setattr(auth, "get_collection", lambda name: RevokedUsers())
    token = create_jwt("leader-id", LEADER["email"], token_version=0)
    response = TestClient(app).get("/api/auth/me", cookies={"access_token": token})
    assert response.status_code == 401


def test_ip_and_user_rate_limits(monkeypatch):
    from api.routes import auth as auth_routes

    class RegistrationUsers:
        async def find_one(self, query):
            return None

        async def insert_one(self, document):
            return None

    monkeypatch.setattr(auth_routes, "get_collection", lambda name: RegistrationUsers())
    client = TestClient(app)
    for index in range(5):
        assert client.post(
            "/api/auth/register",
            json={"name": "User", "email": f"user{index}@example.com", "password": "password"},
        ).status_code == 201
    assert client.post(
        "/api/auth/register",
        json={"name": "User", "email": "blocked@example.com", "password": "password"},
    ).status_code == 429

    limiter.reset()
    trips = FakeTrips(_trip())
    app.dependency_overrides[get_current_user] = _override_user(LEADER)
    app.dependency_overrides[get_trips_collection] = lambda: trips
    token = create_jwt("leader-id", LEADER["email"])
    for index in range(10):
        assert client.post(
            "/api/trips",
            cookies={"access_token": token},
            json={"trip_name": f"Trip {index}", "invited_emails": []},
        ).status_code == 200
    assert client.post(
        "/api/trips",
        cookies={"access_token": token},
        json={"trip_name": "Blocked", "invited_emails": []},
    ).status_code == 429
