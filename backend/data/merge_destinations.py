"""Merge batch*.json destination lists into destinations.json (run from repo: python data/merge_destinations.py)."""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
OUTPUT = DATA_DIR / "destinations.json"


def main() -> None:
    paths = sorted(
        p
        for p in DATA_DIR.glob("batch*.json")
        if p.name != OUTPUT.name and p.is_file()
    )
    if not paths:
        raise SystemExit(f"No batch*.json files found under {DATA_DIR}")

    all_destinations: list[dict] = []
    for filepath in paths:
        with open(filepath, encoding="utf-8") as f:
            chunk = json.load(f)
        if not isinstance(chunk, list):
            raise TypeError(f"{filepath.name}: expected a JSON array, got {type(chunk).__name__}")
        all_destinations.extend(chunk)

    for dest in all_destinations:
        tags = dest.get("vibe_tags")
        if not isinstance(tags, dict):
            continue
        if "adventure" in tags:
            tags["outdoor"] = tags.pop("adventure")

    # If the same id appears in multiple batches, last occurrence wins
    by_id: dict[str, dict] = {}
    for dest in all_destinations:
        by_id[dest["id"]] = dest
    merged = sorted(by_id.values(), key=lambda d: d["id"])

    print(f"Files merged: {len(paths)}")
    print(f"Total rows (before dedupe): {len(all_destinations)}")
    print(f"Total destinations (unique id): {len(merged)}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")

    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
