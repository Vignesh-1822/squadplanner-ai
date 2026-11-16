"""Fill in candidate destinations that were scored before a field existed.

Candidates are computed once, at ``select_destination``, and frozen into the LangGraph
checkpoint. Any field added to the shortlist afterwards — photography, the dataset tags behind
the detail panel — is therefore missing from every trip scored before that change, and the
checkpoint is rewritten on each resume, so backfilling the stored copy does not stick.

Enriching on the way *out* instead fixes old and new trips with the same code path. Images come
from the Mongo cache, so for a destination anyone has seen before this costs nothing.
"""

import functools
import json
import logging
import pathlib
from typing import Any

from tools.destination_images import attach_images, resolve_destination_image

logger = logging.getLogger(__name__)

DESTINATIONS_PATH = pathlib.Path(__file__).parent.parent / "data" / "destinations.json"

# Dataset fields the detail panel reads that older shortlists never stored.
_DATASET_FIELDS = ("best_for", "vibe_tags", "notes", "type", "cost_level")


@functools.lru_cache(maxsize=1)
def _destinations_by_name() -> dict[str, dict]:
    """Name -> dataset row. A completed trip stores only the destination's *name*, so this is
    the only way back to its id, and therefore to its photo."""
    return {str(d.get("name", "")).lower(): d for d in _destinations_by_id().values()}


@functools.lru_cache(maxsize=1)
def _destinations_by_id() -> dict[str, dict]:
    try:
        raw = json.loads(DESTINATIONS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load destinations dataset: %s", exc)
        return {}
    return {str(d.get("id", "")): d for d in raw}


async def enrich_candidates(candidates: list[dict]) -> list[dict]:
    """Add any missing dataset fields and photography to a shortlist, in place."""
    if not candidates:
        return candidates

    dataset = _destinations_by_id()
    for candidate in candidates:
        source = dataset.get(str(candidate.get("id", "")))
        if not source:
            continue
        for field in _DATASET_FIELDS:
            if not candidate.get(field) and source.get(field):
                candidate[field] = source[field]

    try:
        await attach_images(candidates)
    except Exception as exc:  # noqa: BLE001
        # Cards fall back to their type gradient; never worth failing the shortlist over.
        logger.warning("Candidate image lookup failed: %s", exc)

    return candidates


async def destination_hero(destination_name: str | None) -> dict[str, Any]:
    """Photography for a chosen destination, for the trip hub banner.

    Completed trips predate this field and store only the name, so the dataset is searched by
    name rather than the trip carrying an id. The image itself comes from the same cache the
    shortlist uses, so this is normally a single indexed read.
    """
    if not destination_name:
        return {}

    row = _destinations_by_name().get(destination_name.strip().lower())
    if not row:
        return {}

    try:
        found = await resolve_destination_image(
            str(row.get("id", "")), row.get("name", ""), row.get("state", "")
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Hero image lookup failed for %s: %s", destination_name, exc)
        return {}

    return found or {}
