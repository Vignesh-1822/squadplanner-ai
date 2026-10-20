"""Versioned calibration rubrics shared by the human rater and model evaluator."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

RUBRIC_FILES = (
    "itinerary_coherence",
    "fairness_across_members",
    "trip_pitch_quality",
)
_ROOT = Path(__file__).resolve().parent
_ANCHOR_RE = re.compile(
    r"^## ([1-5]) — ([^\n]+)\n(.*?)(?=^## [1-5] — |\Z)",
    flags=re.MULTILINE | re.DOTALL,
)


def load_rubric(name: str) -> dict[str, Any]:
    """Load one rubric into the structure used by the labelling API."""
    if name not in RUBRIC_FILES:
        raise ValueError(f"Unknown rubric {name!r}")
    path = _ROOT / f"{name}.md"
    content = path.read_text(encoding="utf-8")
    title_match = re.search(r"^# (.+)$", content, flags=re.MULTILINE)
    anchors = {
        int(score): {"label": label.strip(), "description": description.strip()}
        for score, label, description in _ANCHOR_RE.findall(content)
    }
    if not title_match or set(anchors) != {1, 2, 3, 4, 5}:
        raise ValueError(f"Rubric {path.name} must contain a title and anchors 1 through 5")
    return {
        "id": name,
        "title": title_match.group(1).strip(),
        "anchors": anchors,
    }


def load_all() -> dict[str, dict[str, Any]]:
    """Return all rubrics in their stable presentation order."""
    return {name: load_rubric(name) for name in RUBRIC_FILES}


def rubric_version() -> str:
    """Hash the exact rubric text so labels cannot outlive their instructions."""
    digest = hashlib.sha256()
    for name in RUBRIC_FILES:
        path = _ROOT / f"{name}.md"
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
