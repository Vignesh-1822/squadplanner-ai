"""The committed calibration set is varied, complete and blind."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.calibration import load_item, load_manifest
from evals.rubrics import rubric_version

_ROOT = Path(__file__).resolve().parent / "calibration"
_BLIND_ITEM_KEYS = {
    "constraint_satisfaction",
    "fairness_score",
    "fairness_scores",
    "budget_status",
    "decision_log",
    "validation_notes",
    "flights",
    "title",
    "purpose",
}


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value), set())
    return set()


def test_calibration_manifest_has_twenty_stratified_items():
    manifest = load_manifest()
    assert manifest["item_count"] == 20
    assert len(manifest["items"]) == 20
    assert len({item["id"] for item in manifest["items"]}) == 20
    assert manifest["rubric_version"] == rubric_version()
    assert set(manifest["quality_band_counts"]) == {"clean", "mixed", "degraded"}
    assert all(count >= 3 for count in manifest["quality_band_counts"].values())

    dimensions = [item["dimensions"] for item in manifest["items"]]
    assert {1, 8} <= {item["group_size"] for item in dimensions}
    assert {2, 14} <= {item["trip_length_days"] for item in dimensions}
    assert sum(bool(item["dietary_restrictions"]) for item in dimensions) >= 4
    assert any(item["budget_spread_usd"] >= 2000 for item in dimensions)
    assert any(item["graph_only"] for item in dimensions)


def test_every_item_is_renderable_and_contains_no_anchoring_fields():
    for entry in load_manifest()["items"]:
        item = load_item(entry["id"])
        assert item["id"] == entry["id"]
        assert item["members"]
        assert item["days"]
        assert item["trip_pitch"]
        assert len(item["per_member_costs"]) == len(item["members"])
        assert {row["member_id"] for row in item["per_member_costs"]} == {
            member["member_id"] for member in item["members"]
        }
        assert not (_keys(item) & _BLIND_ITEM_KEYS)


def test_calibration_json_contains_no_automated_rating_output():
    for path in [_ROOT / "manifest.json", *sorted((_ROOT / "itineraries").glob("*.json"))]:
        data = json.loads(path.read_text(encoding="utf-8"))
        keys = {key.lower() for key in _keys(data)}
        assert not any("judge" in key or "model_score" in key for key in keys), path
