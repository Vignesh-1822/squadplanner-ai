"""Filesystem helpers for the database-free human calibration handoff."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def calibration_root() -> Path:
    override = os.getenv("EVALS_CALIBRATION_DIR")
    return Path(override).expanduser().resolve() if override else Path(__file__).resolve().parent


def manifest_path() -> Path:
    return calibration_root() / "manifest.json"


def itineraries_dir() -> Path:
    return calibration_root() / "itineraries"


def labels_path() -> Path:
    return calibration_root() / "labels.json"


def load_manifest() -> dict[str, Any]:
    path = manifest_path()
    if not path.is_file():
        raise FileNotFoundError("Calibration items have not been built")
    return json.loads(path.read_text(encoding="utf-8"))


def load_item(item_id: str) -> dict[str, Any]:
    manifest = load_manifest()
    known_ids = {str(item["id"]) for item in manifest.get("items", [])}
    if item_id not in known_ids:
        raise KeyError(item_id)
    path = itineraries_dir() / f"{item_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Calibration item {item_id} is missing")
    return json.loads(path.read_text(encoding="utf-8"))


def load_labels() -> dict[str, Any]:
    path = labels_path()
    if not path.is_file():
        return {"rubric_version": None, "labels": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("labels"), list):
        raise ValueError("Calibration labels file must contain a labels list")
    return data
