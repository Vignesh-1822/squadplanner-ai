"""Compact, serialisable event artifacts used by trajectory scorers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


_KEPT_EVENT_TYPES = {
    "on_chain_start",
    "on_chain_end",
    "on_chat_model_start",
    "on_chat_model_end",
    "on_tool_start",
    "on_tool_end",
}


def compact_event(event: dict[str, Any]) -> dict[str, Any] | None:
    if event.get("event") not in _KEPT_EVENT_TYPES:
        return None
    result = {
        "event": event.get("event"),
        "name": event.get("name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": str(event.get("run_id") or ""),
        "parent_ids": [str(run_id) for run_id in (event.get("parent_ids") or [])],
        "tags": list(event.get("tags") or []),
        "metadata": dict(event.get("metadata") or {}),
    }
    data = event.get("data") or {}
    if event.get("event") == "on_tool_start":
        value = data.get("input")
        if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
            result["input"] = value
    return result


def node_sequence(events: list[dict[str, Any]]) -> list[str]:
    return [
        str(event["name"])
        for event in events
        if event.get("event") == "on_chain_start"
        and event.get("metadata", {}).get("langgraph_node")
        and event.get("name") != "LangGraph"
    ]


def count_node(events: list[dict[str, Any]], node: str) -> int:
    return sum(
        1
        for event in events
        if event.get("event") == "on_chain_start" and event.get("name") == node
    )
