"""LangChain callback that aggregates model usage by graph node."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from time import perf_counter
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from evals.telemetry.pricing import calculate_cost


def _usage_from_response(response: Any) -> tuple[dict[str, Any], str]:
    message = None
    generations = getattr(response, "generations", None) or []
    if generations and generations[0]:
        message = getattr(generations[0][0], "message", None)
    usage = dict(getattr(message, "usage_metadata", None) or {})
    llm_output = getattr(response, "llm_output", None) or {}
    token_usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
    input_tokens = int(
        usage.get("input_tokens")
        or token_usage.get("input_tokens")
        or token_usage.get("prompt_tokens")
        or 0
    )
    output_tokens = int(
        usage.get("output_tokens")
        or token_usage.get("output_tokens")
        or token_usage.get("completion_tokens")
        or 0
    )
    details = usage.get("input_token_details") or {}
    cache_read = int(
        details.get("cache_read")
        or details.get("cache_read_tokens")
        or token_usage.get("cache_read_input_tokens")
        or 0
    )
    model = str(
        getattr(message, "response_metadata", {}).get("model")
        or getattr(message, "response_metadata", {}).get("model_name")
        or llm_output.get("model")
        or llm_output.get("model_name")
        or "unknown"
    )
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read,
    }, model


class UsageTracker(BaseCallbackHandler):
    """Accumulate usage; safe when parallel tool/model callbacks complete together."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._starts: dict[Any, tuple[str, float]] = {}
        self._llm_nodes: dict[Any, tuple[str, float]] = {}
        self._durations_ms: defaultdict[str, float] = defaultdict(float)
        self._first_started: float | None = None
        self._last_ended: float | None = None
        self._nodes: defaultdict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cost_usd": 0.0,
                "unpriced_calls": 0,
                "llm_calls": 0,
            }
        )

    def on_chain_start(self, serialized: Any, inputs: Any, **kwargs: Any) -> None:
        now = perf_counter()
        with self._lock:
            if self._first_started is None:
                self._first_started = now
        metadata = kwargs.get("metadata") or {}
        name = str(metadata.get("langgraph_node") or "")
        if not name or str(kwargs.get("name") or name) != name:
            return
        with self._lock:
            self._starts[kwargs.get("run_id")] = (name, now)

    def on_chain_end(self, outputs: Any, **kwargs: Any) -> None:
        with self._lock:
            self._last_ended = perf_counter()
            started = self._starts.pop(kwargs.get("run_id"), None)
            if started:
                name, start = started
                self._durations_ms[name] += (perf_counter() - start) * 1000

    def on_llm_start(self, serialized: Any, prompts: Any, **kwargs: Any) -> None:
        metadata = kwargs.get("metadata") or {}
        now = perf_counter()
        with self._lock:
            if self._first_started is None:
                self._first_started = now
            self._llm_nodes[kwargs.get("run_id")] = (
                str(metadata.get("langgraph_node") or "unattributed"),
                now,
            )

    def on_chat_model_start(self, serialized: Any, messages: Any, **kwargs: Any) -> None:
        self.on_llm_start(serialized, messages, **kwargs)

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        metadata = kwargs.get("metadata") or {}
        usage, model = _usage_from_response(response)
        cost = calculate_cost(model, **usage)
        with self._lock:
            self._last_ended = perf_counter()
            llm_run = self._llm_nodes.pop(kwargs.get("run_id"), None)
            node = str(
                metadata.get("langgraph_node")
                or (llm_run[0] if llm_run else None)
                or "unattributed"
            )
            bucket = self._nodes[node]
            for key, value in usage.items():
                bucket[key] += value
            bucket["llm_calls"] += 1
            if cost["priced"]:
                bucket["cost_usd"] = round(bucket["cost_usd"] + cost["cost_usd"], 8)
            else:
                bucket["unpriced_calls"] += 1
            if node.startswith("refine_agent_") and llm_run:
                bucket["duration_ms"] = round(
                    bucket.get("duration_ms", 0) + (perf_counter() - llm_run[1]) * 1000,
                    3,
                )

    def snapshot(self, durations_ms: dict[str, float] | None = None) -> dict[str, Any]:
        with self._lock:
            nodes = {name: dict(values) for name, values in self._nodes.items()}
            measured = dict(self._durations_ms)
        measured.update(durations_ms or {})
        for node, duration in measured.items():
            nodes.setdefault(node, {})["duration_ms"] = round(duration, 3)
        totals: dict[str, Any] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cost_usd": 0.0,
            "unpriced_calls": 0,
            "llm_calls": 0,
            "duration_ms": 0.0,
        }
        for values in nodes.values():
            for key in totals:
                if key == "duration_ms":
                    continue
                totals[key] += values.get(key, 0)
        totals["cost_usd"] = round(totals["cost_usd"], 8)
        with self._lock:
            if self._first_started is not None and self._last_ended is not None:
                totals["duration_ms"] = round(
                    (self._last_ended - self._first_started) * 1000,
                    3,
                )
        return {"nodes": nodes, "totals": totals}

    def drain(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        with self._lock:
            self._nodes.clear()
            self._durations_ms.clear()
            self._starts.clear()
            self._llm_nodes.clear()
            self._first_started = None
            self._last_ended = None
        return snapshot


def merge_telemetry(existing: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {"nodes": {}, "totals": {}}
    for source in (existing or {}, current):
        for node, values in (source.get("nodes") or {}).items():
            bucket = merged["nodes"].setdefault(node, {})
            for key, value in values.items():
                if isinstance(value, (int, float)):
                    bucket[key] = round(bucket.get(key, 0) + value, 8)
                else:
                    bucket[key] = value
        for key, value in (source.get("totals") or {}).items():
            if isinstance(value, (int, float)):
                merged["totals"][key] = round(merged["totals"].get(key, 0) + value, 8)
            else:
                merged["totals"][key] = value
    return merged


def telemetry_inc_fields(current: dict[str, Any]) -> dict[str, int | float]:
    """Flatten a drained segment for one atomic MongoDB ``$inc`` update."""
    fields: dict[str, int | float] = {}
    for node, values in (current.get("nodes") or {}).items():
        safe_node = str(node).replace(".", "_").replace("$", "_")
        for metric, value in values.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                fields[f"telemetry.nodes.{safe_node}.{metric}"] = value
    for metric, value in (current.get("totals") or {}).items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            fields[f"telemetry.totals.{metric}"] = value
    return fields
