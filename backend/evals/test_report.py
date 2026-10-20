"""Scorecard labelling and live-run signal tests."""

from evals.report import render


def test_offline_report_cannot_be_misread_as_quality():
    text = render({"tier": "offline", "cases": [], "replay_misses": []})
    assert "do NOT measure itinerary quality" in text
    assert "Live run needed: no" in text


def test_replay_miss_requests_live_run():
    text = render(
        {
            "tier": "offline",
            "cases": [],
            "replay_misses": [{"case_id": "changed-prompt", "detail": "miss"}],
        }
    )
    assert "Live run needed: YES" in text
    assert "changed-prompt" in text
