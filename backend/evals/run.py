"""Run the offline or explicitly-enabled live golden tier."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from evals.cases import load_cases
from evals.harness.runner import run_case
from evals.record import local_serpapi_remaining, real_serpapi_remaining
from evals.replay.store import ReplayMiss
from evals.scorers.deterministic import score_all as deterministic_scores
from evals.scorers.trajectory import score_all as trajectory_scores

_ROOT = Path(__file__).resolve().parent


async def run_tier(tier: str) -> dict:
    cases = load_cases(tier)
    if tier == "live":
        if os.getenv("RUN_LIVE_EVALS", "").lower() != "true":
            raise RuntimeError("Live evals spend quota; set RUN_LIVE_EVALS=true to confirm")
        required = sum(len(case["payload"]["members"]) + 1 for case in cases)
        remaining = min(await real_serpapi_remaining(), await local_serpapi_remaining())
        if remaining < required:
            raise RuntimeError(f"Live tier needs about {required} searches; only {remaining} remain")
        os.environ["EVALS_TOOL_MODE"] = "off"
        os.environ["EVALS_LLM_MODE"] = "off"
    else:
        os.environ["EVALS_TOOL_MODE"] = "replay"
        os.environ["EVALS_LLM_MODE"] = "replay"

    output = {"tier": tier, "warning": "", "cases": [], "replay_misses": []}
    if tier == "offline":
        output["warning"] = "Frozen LLM output: code regressions only; not itinerary quality."
    for case in cases:
        try:
            run = await run_case(
                case,
                artifact_path=_ROOT / "fixtures" / "events" / f"{case['id']}.json",
            )
        except ReplayMiss as exc:
            output["replay_misses"].append({"case_id": case["id"], "detail": str(exc)})
            continue
        output["cases"].append(
            {
                "id": case["id"],
                "deterministic": deterministic_scores(run.final_state),
                "trajectory": trajectory_scores(
                    case,
                    run.final_state,
                    run.events,
                    run.tool_calls,
                ),
                "telemetry": run.telemetry,
            }
        )
    (_ROOT / "results").mkdir(exist_ok=True)
    path = _ROOT / "results" / f"{tier}.json"
    path.write_text(json.dumps(output, indent=2, default=str) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_tier("live" if args.live else "offline"))


if __name__ == "__main__":
    main()
