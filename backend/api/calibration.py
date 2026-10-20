"""Admin-only routes for the blind human calibration handoff."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.middleware.authz import require_admin
from evals.calibration import labels_path, load_item, load_labels, load_manifest
from evals.rubrics import load_all, rubric_version

router = APIRouter(prefix="/calibration", tags=["calibration"])


class CriterionLabel(BaseModel):
    score: int = Field(ge=1, le=5)
    notes: str = Field(default="", max_length=2000)


class LabelSubmission(BaseModel):
    item_id: str
    pass_index: Literal[1, 2]
    itinerary_coherence: CriterionLabel
    fairness_across_members: CriterionLabel
    trip_pitch_quality: CriterionLabel


def _allowed_item_ids(manifest: dict, pass_index: int) -> list[str]:
    item_ids = [str(item["id"]) for item in manifest.get("items", [])]
    return item_ids[:3] if pass_index == 2 else item_ids


def _completed_item_ids(labels: dict, pass_index: int) -> list[str]:
    return [
        str(label["item_id"])
        for label in labels.get("labels", [])
        if int(label.get("pass_index", 0)) == pass_index
    ]


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


@router.get("/session")
async def get_calibration_session(
    item_id: str | None = None,
    pass_index: int = Query(default=1, alias="pass", ge=1, le=2),
    current_user: dict = Depends(require_admin),
):
    del current_user
    try:
        manifest = load_manifest()
        labels = load_labels()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    allowed_ids = _allowed_item_ids(manifest, pass_index)
    completed_ids = _completed_item_ids(labels, pass_index)
    if item_id is None:
        item_id = next((candidate for candidate in allowed_ids if candidate not in completed_ids), None)
        if item_id is None and allowed_ids:
            item_id = allowed_ids[-1]
    if item_id not in allowed_ids:
        detail = (
            "The consistency pass is limited to the first three items"
            if pass_index == 2
            else "Calibration item not found"
        )
        raise HTTPException(status_code=400 if pass_index == 2 else 404, detail=detail)
    try:
        item = load_item(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Calibration item not found") from exc
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "pass_index": pass_index,
        "item_ids": allowed_ids,
        "completed_item_ids": completed_ids,
        "item": item,
        "rubrics": load_all(),
        "rubric_version": rubric_version(),
    }


@router.post("/labels", status_code=201)
async def save_calibration_label(
    body: LabelSubmission,
    current_user: dict = Depends(require_admin),
):
    try:
        manifest = load_manifest()
        data = load_labels()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    allowed_ids = _allowed_item_ids(manifest, body.pass_index)
    if body.item_id not in allowed_ids:
        detail = (
            "The consistency pass is limited to the first three items"
            if body.pass_index == 2
            else "Calibration item not found"
        )
        raise HTTPException(
            status_code=400 if body.pass_index == 2 else 404,
            detail=detail,
        )

    version = rubric_version()
    existing_version = data.get("rubric_version")
    if existing_version not in (None, version):
        raise HTTPException(
            status_code=409,
            detail="Rubrics changed after labelling began; archive the old labels before continuing",
        )
    if any(
        label.get("item_id") == body.item_id
        and int(label.get("pass_index", 0)) == body.pass_index
        for label in data.get("labels", [])
    ):
        raise HTTPException(status_code=409, detail="This item is already labelled in this pass")

    ratings = {
        name: getattr(body, name).model_dump()
        for name in (
            "itinerary_coherence",
            "fairness_across_members",
            "trip_pitch_quality",
        )
    }
    record = {
        "item_id": body.item_id,
        "pass_index": body.pass_index,
        "rater_email": current_user.get("email", ""),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "ratings": ratings,
    }
    data = {
        "schema_version": 1,
        "rubric_version": version,
        "labels": [*data.get("labels", []), record],
    }
    _atomic_write(labels_path(), data)
    return {
        "status": "saved",
        "item_id": body.item_id,
        "pass_index": body.pass_index,
    }
