"""Build the blind human-calibration set from recorded planner output."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from datetime import date
from typing import Any

from evals.calibration import calibration_root, itineraries_dir, manifest_path
from evals.cases import load_cases
from evals.harness.runner import run_case
from evals.rubrics import rubric_version
from evals.scorers.deterministic import per_member_costs
from evals.scorers.deterministic import score_all as deterministic_scores
from evals.scorers.trajectory import score_all as trajectory_scores

_STARTING_IDS = (
    "01-01_basic_smoke_completed",
    "02-02_preference_weight_conflict",
    "03-03_natural_language_conflict",
    "04-04_budget_limit_crossing",
    "07-07_long_six_member_high_conflict_trip",
    "09-happy_path_relaxed_mixed_group",
    "10-budget_pressure_group",
    "11-food_restriction_validation",
    "12-nightlife_hard_avoid",
    "13-tight-budget",
    "14-wide-budget-spread",
    "16-diet-vegan",
    "17-diet-halal",
    "19-hard-avoid",
    "21-single-member",
    "22-eight-members",
    "23-two-day",
    "24-fourteen-day",
    "25-opposite-vectors",
    "30-all-outdoor",
)
_REPLACEMENT_ORDER = (
    "13-tight-budget",
    "09-happy_path_relaxed_mixed_group",
    "30-all-outdoor",
    "01-01_basic_smoke_completed",
)
_MINIMUM_BANDS = {"clean": 3, "mixed": 5, "degraded": 5}
_ACTIVITY_FIELDS = (
    "name",
    "category",
    "address",
    "lat",
    "lng",
    "price_level",
    "rating",
    "tags",
)
_ROUTE_FIELDS = (
    "distance_meters",
    "duration_seconds",
    "mode",
    "from_order",
    "to_order",
    "from_label",
    "to_label",
)


def _quality_proxy(
    deterministic: dict[str, dict[str, Any]],
    trajectory: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    deterministic_failures = sorted(
        name
        for name, result in deterministic.items()
        if result.get("scorable", True) and not result.get("passed")
    )
    trajectory_failures = sorted(
        name for name, result in trajectory.items() if not result.get("passed")
    )
    rebuilds = int(trajectory.get("rebuild_bound", {}).get("rebuilds", 0))
    if not deterministic_failures and not trajectory_failures:
        band = "clean"
    elif "rebuild_bound" in trajectory_failures or (
        len(deterministic_failures) + len(trajectory_failures) >= 3
    ):
        band = "degraded"
    else:
        band = "mixed"
    return {
        "band": band,
        "deterministic": {
            name: {
                "passed": bool(result.get("passed")),
                "scorable": bool(result.get("scorable", True)),
            }
            for name, result in sorted(deterministic.items())
        },
        "trajectory": {
            name: {"passed": bool(result.get("passed"))}
            for name, result in sorted(trajectory.items())
        },
        "deterministic_failures": deterministic_failures,
        "trajectory_failures": trajectory_failures,
        "itinerary_rebuilds": rebuilds,
    }


def _dimensions(case: dict[str, Any]) -> dict[str, Any]:
    payload = case["payload"]
    members = payload["members"]
    budgets = [float(member["budget_usd"]) for member in members]
    restrictions = sorted(
        {
            str(restriction)
            for member in members
            for restriction in member.get("food_restrictions", [])
        }
    )
    duration = (
        date.fromisoformat(payload["end_date"]) - date.fromisoformat(payload["start_date"])
    ).days
    return {
        "group_size": len(members),
        "trip_length_days": duration,
        "dietary_restrictions": restrictions,
        "restricted_member_count": sum(
            bool(member.get("food_restrictions")) for member in members
        ),
        "budget_min_usd": min(budgets),
        "budget_max_usd": max(budgets),
        "budget_spread_usd": max(budgets) - min(budgets),
        "graph_only": bool(case.get("graph_only")),
    }


def _select_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {record["case"]["id"]: record for record in records}
    selected_ids = [case_id for case_id in _STARTING_IDS if case_id in by_id]
    if len(selected_ids) != 20:
        raise ValueError("The calibration starting set must resolve to exactly 20 cases")

    def counts() -> Counter[str]:
        return Counter(by_id[case_id]["quality"]["band"] for case_id in selected_ids)

    for band, minimum in _MINIMUM_BANDS.items():
        while counts()[band] < minimum:
            candidate = next(
                (
                    record
                    for record in records
                    if record["quality"]["band"] == band
                    and record["case"]["id"] not in selected_ids
                ),
                None,
            )
            if candidate is None:
                raise ValueError(f"Not enough {band} cases to stratify calibration set")
            current_counts = counts()
            replace_id = next(
                (
                    case_id
                    for case_id in _REPLACEMENT_ORDER
                    if case_id in selected_ids
                    and current_counts[by_id[case_id]["quality"]["band"]]
                    > _MINIMUM_BANDS[by_id[case_id]["quality"]["band"]]
                ),
                None,
            )
            if replace_id is None:
                raise ValueError(f"Could not make room for required {band} case")
            selected_ids[selected_ids.index(replace_id)] = candidate["case"]["id"]

    order = {record["case"]["id"]: index for index, record in enumerate(records)}
    return sorted((by_id[case_id] for case_id in selected_ids), key=lambda item: order[item["case"]["id"]])


def _whitelist_mapping(value: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {field: value[field] for field in fields if field in value}


def _calibration_item(record: dict[str, Any]) -> dict[str, Any]:
    case = record["case"]
    state = record["run"].final_state
    payload = case["payload"]
    members = [
        _whitelist_mapping(
            member,
            (
                "member_id",
                "name",
                "origin_city",
                "budget_usd",
                "food_restrictions",
                "preference_notes",
                "preference_vector",
                "is_leader",
            ),
        )
        for member in state.get("members", [])
    ]
    days = []
    for day in state.get("days", []):
        activities = [
            _whitelist_mapping(activity, _ACTIVITY_FIELDS)
            if isinstance(activity, dict)
            else {"name": str(activity)}
            for activity in day.get("activities", [])
        ]
        days.append(
            {
                **_whitelist_mapping(
                    day,
                    (
                        "day_number",
                        "date",
                        "neighborhood",
                        "meals",
                        "estimated_day_cost_usd",
                        "schedule",
                        "rationale",
                        "constraint_notes",
                        "total_travel_minutes",
                    ),
                ),
                "activities": activities,
                "routes": [
                    _whitelist_mapping(route, _ROUTE_FIELDS)
                    for route in day.get("routes", [])
                    if isinstance(route, dict)
                ],
            }
        )
    cost_rows = list(per_member_costs(state).values())
    return {
        "id": case["id"],
        "group_notes": payload.get("group_notes", ""),
        "members": members,
        "start_date": state["start_date"],
        "end_date": state["end_date"],
        "trip_duration_days": state["trip_duration_days"],
        "destination": {
            "name": state.get("selected_destination"),
            "coords": state.get("selected_destination_coords"),
        },
        "hotel": _whitelist_mapping(
            state.get("hotel"),
            (
                "name",
                "address",
                "price_per_night_usd",
                "total_price_usd",
                "rating",
                "is_estimated",
            ),
        ),
        "weather": _whitelist_mapping(
            state.get("weather"),
            (
                "destination",
                "date_range",
                "avg_temp_c",
                "precipitation_mm",
                "summary",
            ),
        ),
        "days": days,
        "trip_pitch": state.get("trip_pitch") or "",
        "per_member_costs": cost_rows,
        "provenance": {
            "source_case_id": case["id"],
            "source_tier": "offline",
            "planner_output": "Recorded live model output replayed without network access.",
            "flight_data": "K-002 baseline: fixed $300 estimated flight per member.",
        },
    }


def _rationale(record: dict[str, Any]) -> str:
    dimensions = record["dimensions"]
    quality = record["quality"]
    diets = ", ".join(dimensions["dietary_restrictions"]) or "none"
    issues = quality["deterministic_failures"] + quality["trajectory_failures"]
    issue_text = ", ".join(issues) if issues else "no scored failures"
    return (
        f"{quality['band']} quality proxy ({issue_text}); "
        f"{dimensions['group_size']} members, {dimensions['trip_length_days']} days, "
        f"dietary load {diets}, budget spread ${dimensions['budget_spread_usd']:.0f}."
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


async def build() -> dict[str, Any]:
    os.environ["EVALS_TOOL_MODE"] = "replay"
    os.environ["EVALS_LLM_MODE"] = "replay"
    records: list[dict[str, Any]] = []
    for case in load_cases("offline"):
        run = await run_case(case)
        deterministic = deterministic_scores(run.final_state)
        trajectory = trajectory_scores(case, run.final_state, run.events, run.tool_calls)
        records.append(
            {
                "case": case,
                "run": run,
                "quality": _quality_proxy(deterministic, trajectory),
                "dimensions": _dimensions(case),
            }
        )

    selected = _select_records(records)
    item_dir = itineraries_dir()
    item_dir.mkdir(parents=True, exist_ok=True)
    selected_ids = {record["case"]["id"] for record in selected}
    for stale in item_dir.glob("*.json"):
        if stale.stem not in selected_ids:
            stale.unlink()
    for record in selected:
        item = _calibration_item(record)
        _write_json(item_dir / f"{item['id']}.json", item)

    manifest = {
        "schema_version": 1,
        "source_tier": "offline",
        "rubric_version": rubric_version(),
        "item_count": len(selected),
        "quality_band_counts": dict(
            sorted(Counter(record["quality"]["band"] for record in selected).items())
        ),
        "items": [
            {
                "id": record["case"]["id"],
                "title": record["case"]["title"],
                "dimensions": record["dimensions"],
                "quality_proxy": record["quality"],
                "selection_rationale": _rationale(record),
            }
            for record in selected
        ],
    }
    _write_json(manifest_path(), manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    manifest = asyncio.run(build())
    print(
        f"Built {manifest['item_count']} blind calibration itineraries in "
        f"{calibration_root()} with quality bands {manifest['quality_band_counts']}."
    )


if __name__ == "__main__":
    main()
