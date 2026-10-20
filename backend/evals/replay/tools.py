"""Tool replay helpers and fixture-integrity checks."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from typing import Iterator

from evals.modes import EvalMode, tool_mode
from evals.replay.store import ReplayStore

_STORE = ReplayStore("tools")
NO_REPLAY = object()
_TOOL_CALLS: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "evals_tool_calls",
    default=None,
)


class ReplayRecordingError(ValueError):
    """Raised instead of degrading when a recording is not genuine live data."""


def replay_tool(operation: str, request: dict[str, Any]) -> Any:
    calls = _TOOL_CALLS.get()
    if calls is not None:
        calls.append({"operation": operation, "request": request})
    mode = tool_mode()
    if mode is EvalMode.REPLAY:
        return _STORE.load(operation, request)
    if mode is EvalMode.RECORD:
        if _STORE.contains(operation, request):
            response = _STORE.load(operation, request)
            try:
                validate_recorded_tool_response(operation, response, request)
            except ReplayRecordingError:
                return NO_REPLAY
            return response
    return NO_REPLAY


@contextmanager
def capture_tool_calls() -> Iterator[list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []
    token = _TOOL_CALLS.set(calls)
    try:
        yield calls
    finally:
        _TOOL_CALLS.reset(token)


def validate_recorded_tool_response(
    operation: str,
    response: Any,
    request: dict[str, Any] | None = None,
) -> None:
    if isinstance(response, dict) and response.get("is_estimated") is True:
        destination = str((request or {}).get("destination", ""))
        city_name_k002 = bool(
            destination
            and not (len(destination) == 3 and destination.isalpha() and destination.isupper())
            and not destination.startswith(("/m", "/g"))
        )
        if operation == "search_flights" and city_name_k002:
            # K-002: production currently passes city names to arrival_id. The
            # baseline intentionally preserves and labels that fallback.
            return
        raise ReplayRecordingError(f"Refusing to record estimated response from {operation}")
    if operation == "fetch_activities_by_category" and not response:
        raise ReplayRecordingError("Refusing to record an empty Google Places response")
    if operation == "get_route" and isinstance(response, dict):
        if not response.get("distance_meters") and not response.get("duration_seconds"):
            same_point = bool(
                request
                and float(request["origin_lat"]) == float(request["dest_lat"])
                and float(request["origin_lng"]) == float(request["dest_lng"])
            )
            if not same_point:
                raise ReplayRecordingError("Refusing to record an all-zero Google Routes response")
    if operation == "fetch_weather" and isinstance(response, dict):
        if response.get("summary") == "Weather data unavailable":
            raise ReplayRecordingError("Refusing to record unavailable weather")


def record_tool(operation: str, request: dict[str, Any], response: Any) -> None:
    if tool_mode() is not EvalMode.RECORD:
        return
    validate_recorded_tool_response(operation, response, request)
    _STORE.save(operation, request, response)
