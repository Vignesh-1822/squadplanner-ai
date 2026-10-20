"""Tests for the judge-agreement maths.

The degenerate-input handling matters more than the happy path: a rater who used a
single score for every item makes quadratic-weighted kappa collapse to 0 or 0/0 no
matter how the judge performed, and reporting that 0 as a measurement would be
worse than reporting nothing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from evals.calibrate import band, compute, quadratic_weighted_kappa, render


def test_perfect_agreement_is_one() -> None:
    scores = [1, 2, 3, 4, 5, 3, 2]
    result = quadratic_weighted_kappa(scores, scores)
    assert result["kappa"] == pytest.approx(1.0)
    assert result["degenerate"] is False


def test_constant_human_is_flagged_degenerate() -> None:
    result = quadratic_weighted_kappa([3] * 6, [1, 2, 3, 4, 5, 4])
    assert result["degenerate"] is True
    assert "human" in result["reason"]
    # The coefficient is exactly zero by construction, not by measurement.
    assert result["kappa"] == pytest.approx(0.0)


def test_constant_judge_is_flagged_degenerate() -> None:
    result = quadratic_weighted_kappa([1, 2, 3, 4, 5, 4], [4] * 6)
    assert result["degenerate"] is True
    assert "judge" in result["reason"]


def test_both_constant_is_undefined_not_zero() -> None:
    result = quadratic_weighted_kappa([3] * 5, [3] * 5)
    assert result["kappa"] is None
    assert result["degenerate"] is True


def test_disagreement_weighting_is_quadratic() -> None:
    """A far miss must cost more than a near one on the same marginals."""
    near = quadratic_weighted_kappa([1, 2, 4, 5], [1, 3, 4, 5])
    far = quadratic_weighted_kappa([1, 2, 4, 5], [1, 5, 4, 5])
    assert near["kappa"] > far["kappa"]


def test_empty_input_does_not_divide_by_zero() -> None:
    assert quadratic_weighted_kappa([], [])["kappa"] is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-0.3, "worse than chance"),
        (0.10, "slight"),
        (0.31, "fair"),
        (0.45, "moderate"),
        (0.70, "substantial"),
        (0.95, "almost perfect"),
    ],
)
def test_interpretation_bands(value: float, expected: str) -> None:
    assert band(value) == expected


def test_missing_labels_exit_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The command is in the success criteria, so it must be runnable before labels exist."""
    monkeypatch.setenv("EVALS_CALIBRATION_DIR", str(tmp_path))
    (tmp_path / "manifest.json").write_text(json.dumps({"item_count": 0, "items": []}))
    result = compute()
    assert result["status"] == "awaiting_human_labels"
    assert render(result) == "awaiting human labels"


def test_committed_baseline_reports_every_criterion() -> None:
    """Guard the committed numbers so a regression in the maths is visible."""
    if os.getenv("EVALS_CALIBRATION_DIR"):
        pytest.skip("calibration directory overridden")
    result = compute()
    assert result["status"] == "ok"
    assert result["first_pass_labelled"] == 20
    assert result["second_pass_labelled"] == 3
    assert not result["rubric_drift"], "rubrics changed since the labels were recorded"
    criteria = result["judge"]["criteria"]
    assert set(criteria) == {
        "itinerary_coherence",
        "fairness_across_members",
        "trip_pitch_quality",
    }
    # Trip-pitch quality is degenerate by construction; the other two are not.
    assert criteria["trip_pitch_quality"]["degenerate"] is True
    assert criteria["fairness_across_members"]["degenerate"] is False
