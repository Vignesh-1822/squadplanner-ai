"""Replay-layer regression tests; no network or database."""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from evals.replay import llm as llm_replay
from evals.replay import tools as tool_replay
from evals.replay.store import ReplayMiss, ReplayStore
from evals.telemetry.usage import UsageTracker
from evals import modes


class FakeModel:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, value, config=None, **kwargs):
        self.calls += 1
        return AIMessage(
            content=f"reply:{value}",
            usage_metadata={"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
        )

    async def ainvoke(self, value, config=None, **kwargs):
        return self.invoke(value, config=config, **kwargs)

    def bind_tools(self, tools, **kwargs):
        return self


def test_modes_fall_back_to_loaded_settings(monkeypatch):
    from config import settings

    monkeypatch.delenv("EVALS_TOOL_MODE", raising=False)
    monkeypatch.setattr(settings, "evals_tool_mode", "record")
    assert modes.tool_mode() is modes.EvalMode.RECORD


def test_store_round_trip_and_exact_request(tmp_path: Path):
    store = ReplayStore("test", root=tmp_path)
    store.save("operation", {"value": 1}, {"answer": 2})
    assert store.load("operation", {"value": 1}) == {"answer": 2}
    with pytest.raises(ReplayMiss):
        store.load("operation", {"value": 2})


def test_llm_prompt_edit_is_a_replay_miss(monkeypatch, tmp_path: Path):
    store = ReplayStore("llm", root=tmp_path)
    monkeypatch.setattr(llm_replay, "_STORE", store)
    monkeypatch.setenv("EVALS_LLM_MODE", "record")
    target = FakeModel()
    wrapped = llm_replay.ReplayLLM(target)
    recorded = wrapped.invoke("original prompt")
    assert target.calls == 1

    monkeypatch.setenv("EVALS_LLM_MODE", "replay")
    assert wrapped.invoke("original prompt").content == recorded.content
    assert target.calls == 1
    with pytest.raises(ReplayMiss):
        wrapped.invoke("edited prompt")


@pytest.mark.asyncio
async def test_llm_async_and_bind_tools_replay(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(llm_replay, "_STORE", ReplayStore("llm", root=tmp_path))
    monkeypatch.setenv("EVALS_LLM_MODE", "record")
    wrapped = llm_replay.ReplayLLM(FakeModel()).bind_tools([{"name": "tool"}])
    first = await wrapped.ainvoke("prompt")
    monkeypatch.setenv("EVALS_LLM_MODE", "replay")
    assert (await wrapped.ainvoke("prompt")).content == first.content


@pytest.mark.asyncio
async def test_replayed_out_of_graph_call_uses_explicit_callbacks(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(llm_replay, "_STORE", ReplayStore("llm", root=tmp_path))
    wrapped = llm_replay.ReplayLLM(FakeModel())
    monkeypatch.setenv("EVALS_LLM_MODE", "record")
    await wrapped.ainvoke("refinement")

    tracker = UsageTracker()
    config = {
        "callbacks": [tracker],
        "metadata": {"langgraph_node": "refine_agent_planner"},
    }
    monkeypatch.setenv("EVALS_LLM_MODE", "replay")
    await wrapped.ainvoke("refinement", config=config)
    assert tracker.snapshot()["nodes"]["refine_agent_planner"]["input_tokens"] == 2


def test_bind_options_participate_in_replay_key(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(llm_replay, "_STORE", ReplayStore("llm", root=tmp_path))
    monkeypatch.setenv("EVALS_LLM_MODE", "record")
    llm_replay.ReplayLLM(FakeModel()).bind_tools(
        [{"name": "tool"}],
        tool_choice="auto",
    ).invoke("prompt")
    monkeypatch.setenv("EVALS_LLM_MODE", "replay")
    with pytest.raises(ReplayMiss):
        llm_replay.ReplayLLM(FakeModel()).bind_tools(
            [{"name": "tool"}],
            tool_choice="any",
        ).invoke("prompt")


@pytest.mark.asyncio
async def test_tool_replay_short_circuits_mongo_and_network(monkeypatch, tmp_path: Path):
    store = ReplayStore("tools", root=tmp_path)
    request = {
        "origin": "ORD",
        "destination": "Test City",
        "depart_date": "2026-09-08",
        "return_date": "2026-09-11",
        "adults": 1,
    }
    store.save(
        "search_flights",
        request,
        {
            "member_id": "",
            "origin": "ORD",
            "destination": "Test City",
            "price_usd": 300,
            "airline": "Estimated",
            "depart_time": "2026-09-08T08:00:00",
            "return_time": "2026-09-11T18:00:00",
            "is_estimated": True,
        },
    )
    monkeypatch.setattr(tool_replay, "_STORE", store)
    monkeypatch.setenv("EVALS_TOOL_MODE", "replay")

    import tools.serpapi as serpapi

    monkeypatch.setattr(
        serpapi,
        "get_collection",
        lambda _name: (_ for _ in ()).throw(AssertionError("Mongo must not be touched")),
    )
    result = await serpapi.search_flights("ORD", "Test City", "2026-09-08", "2026-09-11")
    assert result["airline"] == "Estimated"


def test_tool_replay_preserves_recorded_none(monkeypatch, tmp_path: Path):
    store = ReplayStore("tools", root=tmp_path)
    request = {"query": "missing"}
    store.save("find_place_by_text", request, None)
    monkeypatch.setattr(tool_replay, "_STORE", store)
    monkeypatch.setenv("EVALS_TOOL_MODE", "replay")
    assert tool_replay.replay_tool("find_place_by_text", request) is None
