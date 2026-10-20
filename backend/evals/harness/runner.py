"""Unattended graph runner with repeated HITL resolution and event capture."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.types import Command

from evals.harness.events import compact_event
from evals.harness.graph import build_eval_graph
from evals.replay.tools import capture_tool_calls
from evals.replay.store import ReplayMiss, capture_replay_misses
from evals.tracing import build_callbacks


@dataclass
class EvalRun:
    final_state: dict[str, Any]
    events: list[dict[str, Any]]
    telemetry: dict[str, Any]
    hitl_resolutions: int
    tool_calls: list[dict[str, Any]]


def _resume_payload(snapshot: Any, choice: int | str) -> dict[str, Any]:
    candidates = list(snapshot.values.get("candidate_destinations") or [])
    if isinstance(choice, int):
        try:
            selected = candidates[choice]
        except IndexError as exc:
            raise ValueError(f"HITL choice index {choice} is outside {len(candidates)} candidates") from exc
    else:
        selected = next(
            (candidate for candidate in candidates if candidate.get("id") == choice or candidate.get("name") == choice),
            None,
        )
        if selected is None:
            raise ValueError(f"HITL choice {choice!r} is not among the candidates")
    return {
        "selected_destination": selected["name"],
        "selected_destination_coords": selected["coords"],
    }


async def run_case(
    case: dict[str, Any],
    *,
    graph: Any | None = None,
    artifact_path: Path | None = None,
) -> EvalRun:
    graph = graph or build_eval_graph()
    case_id = str(case["id"])
    callbacks, usage = build_callbacks(case_id)
    config = {
        "configurable": {"thread_id": case_id},
        "callbacks": callbacks,
        "metadata": {"trip_id": case_id, "eval_tier": case.get("tier", "offline")},
        "recursion_limit": 100,
    }
    graph_input: Any = dict(case["initial_state"])
    choices = list(case.get("hitl_choices") or [])
    events: list[dict[str, Any]] = []
    resolutions = 0

    with capture_tool_calls() as tool_calls:
        with capture_replay_misses() as replay_misses:
            while True:
                async for event in graph.astream_events(graph_input, config=config, version="v2"):
                    compacted = compact_event(event)
                    if compacted:
                        events.append(compacted)
                snapshot = await graph.aget_state(config)
                if snapshot and "city_selection_hitl" in (snapshot.next or ()):
                    if resolutions >= len(choices):
                        raise ValueError(
                            f"{case_id} reached HITL {resolutions + 1} times but declares only "
                            f"{len(choices)} hitl_choices"
                        )
                    graph_input = Command(resume=_resume_payload(snapshot, choices[resolutions]))
                    resolutions += 1
                    continue
                if not snapshot or snapshot.next:
                    raise RuntimeError(f"{case_id} did not reach a completed graph state")
                break
    if replay_misses:
        raise ReplayMiss(
            f"{case_id} swallowed {len(replay_misses)} replay miss(es): "
            + "; ".join(replay_misses)
        )

    run = EvalRun(
        final_state=dict(snapshot.values),
        events=events,
        telemetry=usage.snapshot(),
        hitl_resolutions=resolutions,
        tool_calls=tool_calls,
    )
    if artifact_path:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            json.dumps(
                {
                    "case_id": case_id,
                    "events": events,
                    "telemetry": run.telemetry,
                    "hitl_resolutions": resolutions,
                    "tool_calls": tool_calls,
                },
                indent=2,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )
    return run
