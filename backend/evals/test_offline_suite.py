"""The 30-case, no-network offline gate."""

from __future__ import annotations

import pytest

from evals.cases import load_cases
from evals.harness.runner import run_case
from evals.scorers.deterministic import score_all as deterministic_scores
from evals.scorers.trajectory import score_all as trajectory_scores


@pytest.mark.asyncio
async def test_all_offline_cases_execute_and_score(monkeypatch):
    monkeypatch.setenv("EVALS_TOOL_MODE", "replay")
    monkeypatch.setenv("EVALS_LLM_MODE", "replay")
    cases = load_cases("offline")
    assert len(cases) == 30

    for case in cases:
        run = await run_case(case)
        deterministic = deterministic_scores(run.final_state)
        trajectory = trajectory_scores(case, run.final_state, run.events, run.tool_calls)

        # Product-promise scorers may be red in a truthful baseline. The gate
        # asserts they all ran and returned inspectable measurements.
        assert all("passed" in result and "detail" in result for result in deterministic.values())
        assert trajectory["expected_nodes"]["passed"], case["id"]
        assert trajectory["tool_arguments"]["passed"], case["id"]
