"""Admin-only calibration routes persist labels without exposing them."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.middleware.auth import get_current_user
from main import app

ADMIN = {"email": "admin@example.com", "is_admin": True}
MEMBER = {"email": "member@example.com", "is_admin": False}


def _override_user(user: dict[str, Any]):
    async def dependency():
        return user

    return dependency


def _payload(item_id: str = "item-1", pass_index: int = 1, score: int = 4) -> dict:
    return {
        "item_id": item_id,
        "pass_index": pass_index,
        "itinerary_coherence": {"score": score, "notes": "Coherence note"},
        "fairness_across_members": {"score": score, "notes": "Fairness note"},
        "trip_pitch_quality": {"score": score, "notes": "Pitch note"},
    }


def _contains_score_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key == "score" or _contains_score_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_score_key(item) for item in value)
    return False


@pytest.fixture(autouse=True)
def calibration_files(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALS_CALIBRATION_DIR", str(tmp_path))
    items = [{"id": f"item-{index}", "title": f"Item {index}"} for index in range(1, 5)]
    (tmp_path / "manifest.json").write_text(
        json.dumps({"item_count": 4, "items": items}),
        encoding="utf-8",
    )
    item_dir = tmp_path / "itineraries"
    item_dir.mkdir()
    for entry in items:
        (item_dir / f"{entry['id']}.json").write_text(
            json.dumps(
                {
                    "id": entry["id"],
                    "members": [{"member_id": "a", "name": "A"}],
                    "days": [{"day_number": 1, "schedule": []}],
                    "per_member_costs": [{"member_id": "a"}],
                    "trip_pitch": "A test pitch",
                }
            ),
            encoding="utf-8",
        )
    app.dependency_overrides.clear()
    yield tmp_path
    app.dependency_overrides.clear()


def test_calibration_routes_require_admin():
    client = TestClient(app)
    assert client.get("/api/calibration/session").status_code == 401

    app.dependency_overrides[get_current_user] = _override_user(MEMBER)
    assert client.get("/api/calibration/session").status_code == 403

    app.dependency_overrides[get_current_user] = _override_user(ADMIN)
    assert client.get("/api/calibration/session").status_code == 200


def test_label_save_is_atomic_resumable_and_blind(calibration_files):
    app.dependency_overrides[get_current_user] = _override_user(ADMIN)
    client = TestClient(app)

    before = client.get("/api/calibration/session?item_id=item-1&pass=1")
    assert before.status_code == 200
    assert before.json()["completed_item_ids"] == []
    assert not _contains_score_key(before.json())

    saved = client.post("/api/calibration/labels", json=_payload())
    assert saved.status_code == 201
    label_file = json.loads((calibration_files / "labels.json").read_text(encoding="utf-8"))
    assert label_file["labels"][0]["rater_email"] == ADMIN["email"]
    assert label_file["labels"][0]["ratings"]["itinerary_coherence"]["score"] == 4
    assert not list(calibration_files.glob(".labels.json.*.tmp"))

    after = client.get("/api/calibration/session?item_id=item-2&pass=1")
    assert after.status_code == 200
    assert after.json()["completed_item_ids"] == ["item-1"]
    assert not _contains_score_key(after.json())
    assert client.post("/api/calibration/labels", json=_payload()).status_code == 409


def test_label_validation_and_pass_two_bounds():
    app.dependency_overrides[get_current_user] = _override_user(ADMIN)
    client = TestClient(app)

    assert client.post(
        "/api/calibration/labels",
        json=_payload(item_id="item-1", score=6),
    ).status_code == 422
    assert client.post(
        "/api/calibration/labels",
        json=_payload(item_id="missing"),
    ).status_code == 404
    assert client.post(
        "/api/calibration/labels",
        json=_payload(item_id="item-4", pass_index=2),
    ).status_code == 400
    assert client.get(
        "/api/calibration/session?item_id=item-4&pass=2"
    ).status_code == 400
