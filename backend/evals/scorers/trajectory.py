"""Free process scorers over compact ``astream_events`` artifacts."""

from __future__ import annotations

from datetime import date
from typing import Any

from evals.harness.events import count_node, node_sequence
from tools.google_places import CATEGORY_TYPE_MAP

CORE_SEQUENCE = [
    "parse_input",
    "extract_preference_constraints",
    "select_destination",
    "city_selection_hitl",
    "dynamic_tool_selection",
    "parallel_data_fetch",
    "budget_analysis",
    "search_hotel",
    "run_itinerary_node",
    "compute_fairness",
    "assemble_output",
]


def _ordered_subsequence(expected: list[str], actual: list[str]) -> bool:
    position = 0
    for value in actual:
        if position < len(expected) and value == expected[position]:
            position += 1
    return position == len(expected)


def expected_nodes(events: list[dict[str, Any]]) -> dict[str, Any]:
    actual = node_sequence(events)
    return {
        "passed": _ordered_subsequence(CORE_SEQUENCE, actual),
        "detail": "All orchestrator nodes appeared in production order; retries may add repeats.",
        "sequence": actual,
    }


def retry_routes(case: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    destination_runs = count_node(events, "select_destination")
    hotel_runs = count_node(events, "search_hotel")
    budget_fired = destination_runs > 1
    fairness_fired = hotel_runs > 1
    return {
        "passed": (
            budget_fired == bool(case.get("expect_budget_retry"))
            and fairness_fired == bool(case.get("expect_fairness_retry"))
        ),
        "detail": "Retry presence matches the case declaration.",
        "budget_retry_fired": budget_fired,
        "fairness_retry_fired": fairness_fired,
        "destination_runs": destination_runs,
        "hotel_runs": hotel_runs,
    }


def rebuild_bound(events: list[dict[str, Any]]) -> dict[str, Any]:
    builds = count_node(events, "build_itinerary")
    rebuilds = max(builds - 1, 0)
    return {
        "passed": rebuilds < 2,
        "detail": "Fewer than two rebuilds means the validation loop did not exhaust its bound.",
        "builds": builds,
        "rebuilds": rebuilds,
        "bound_exhausted": rebuilds >= 2,
    }


def tool_arguments(
    case: dict[str, Any],
    state: dict[str, Any],
    calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    errors = []
    for call in calls or []:
        operation = call["operation"]
        request = call["request"]
        for key in ("start_date", "end_date", "depart_date", "return_date", "check_in", "check_out"):
            if key in request:
                try:
                    date.fromisoformat(str(request[key]))
                except ValueError:
                    errors.append(f"{operation}.{key} is not ISO")
        coordinates = []
        if isinstance(request.get("coords"), dict):
            coordinates.append(request["coords"])
        if operation == "get_route":
            coordinates.extend(
                [
                    {"lat": request.get("origin_lat"), "lng": request.get("origin_lng")},
                    {"lat": request.get("dest_lat"), "lng": request.get("dest_lng")},
                ]
            )
        for coords in coordinates:
            if not all(isinstance(coords.get(key), (int, float)) for key in ("lat", "lng")):
                errors.append(f"{operation} has non-numeric coordinates")
        unknown = set(request.get("categories") or []) - set(CATEGORY_TYPE_MAP)
        if unknown:
            errors.append(f"{operation} has unknown categories: {sorted(unknown)}")
    if not calls:
        errors.append("no replay-bound tool calls were captured")
    return {"passed": not errors, "detail": "Tool-bound inputs have valid dates, coordinates and categories.", "errors": errors}


def score_all(
    case: dict[str, Any],
    state: dict[str, Any],
    events: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    return {
        "expected_nodes": expected_nodes(events),
        "retry_routes": retry_routes(case, events),
        "rebuild_bound": rebuild_bound(events),
        "tool_arguments": tool_arguments(case, state, tool_calls),
    }
