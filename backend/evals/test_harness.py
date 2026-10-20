"""Database-free runner and repeated-HITL tests."""

from types import SimpleNamespace

import pytest
from langgraph.types import Command

from evals.harness.runner import run_case
from evals.harness.events import compact_event


class FakeInterruptingGraph:
    def __init__(self) -> None:
        self.invocations = 0

    async def astream_events(self, graph_input, config, version):
        if self.invocations:
            assert isinstance(graph_input, Command)
        self.invocations += 1
        yield {
            "event": "on_chain_start",
            "name": "select_destination",
            "metadata": {"langgraph_node": "select_destination"},
        }

    async def aget_state(self, config):
        if self.invocations <= 2:
            return SimpleNamespace(
                next=("city_selection_hitl",),
                values={
                    "candidate_destinations": [
                        {"id": "city", "name": "City", "coords": {"lat": 1.0, "lng": 2.0}}
                    ]
                },
            )
        return SimpleNamespace(next=(), values={"trip_id": "repeated-hitl", "days": []})


@pytest.mark.asyncio
async def test_runner_resolves_every_hitl_pause(monkeypatch):
    monkeypatch.setenv("EVALS_TOOL_MODE", "replay")
    monkeypatch.setenv("EVALS_LLM_MODE", "replay")
    graph = FakeInterruptingGraph()
    run = await run_case(
        {
            "id": "repeated-hitl",
            "tier": "offline",
            "initial_state": {},
            "hitl_choices": [0, 0],
        },
        graph=graph,
    )
    assert run.hitl_resolutions == 2
    assert graph.invocations == 3


@pytest.mark.asyncio
async def test_runner_fails_instead_of_hanging_when_choices_run_out(monkeypatch):
    monkeypatch.setenv("EVALS_TOOL_MODE", "replay")
    monkeypatch.setenv("EVALS_LLM_MODE", "replay")
    with pytest.raises(ValueError, match="declares only 1"):
        await run_case(
            {
                "id": "repeated-hitl",
                "tier": "offline",
                "initial_state": {},
                "hitl_choices": [0],
            },
            graph=FakeInterruptingGraph(),
        )


def test_event_artifact_drops_stream_chunks():
    assert compact_event({"event": "on_chat_model_stream", "name": "model"}) is None
    assert compact_event({"event": "on_chain_start", "name": "node", "metadata": {}})
