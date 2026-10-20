"""Fixture recorder with an independent 40-search SerpAPI ceiling."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any

import httpx

from config import settings
from db.client import get_collection
from evals.cases import load_cases
from evals.harness.runner import run_case
from evals.modes import EvalMode, tool_mode

MAX_RECORDING_SEARCHES = 40
_searches_used = 0


def consume_serpapi_search() -> None:
    global _searches_used
    if tool_mode() is not EvalMode.RECORD:
        return
    if _searches_used >= MAX_RECORDING_SEARCHES:
        raise RuntimeError(f"Fixture recording stopped at its {MAX_RECORDING_SEARCHES}-search cap")
    _searches_used += 1


async def real_serpapi_remaining() -> int:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            "https://serpapi.com/account.json",
            params={"api_key": settings.serpapi_key},
        )
    response.raise_for_status()
    data = response.json()
    return int(data.get("total_searches_left", 0))


async def local_serpapi_remaining() -> int:
    from datetime import datetime, timezone

    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    document = await get_collection("api_usage").find_one(
        {"type": "serpapi_usage", "month": current_month}
    )
    used = int(document.get("calls_used", 0)) if document else 0
    return max(settings.serpapi_monthly_hard_limit - used, 0)


def conservative_search_plan(cases: list[dict[str, Any]]) -> int:
    """Count uncached flight/hotel requests assuming one destination per case.

    Actual recording normally uses fewer because Mongo's API cache and fixture
    reuse satisfy identical requests.
    """
    keys = set()
    for case in cases:
        payload = case["payload"]
        window = (payload["start_date"], payload["end_date"])
        for member in payload["members"]:
            keys.add(("flight", member["origin_city"], *window))
        keys.add(("hotel", *window))
    return len(keys)


async def record(tier: str, limit: int | None = None) -> None:
    cases = load_cases(tier)
    if limit:
        cases = cases[:limit]
    planned = conservative_search_plan(cases)
    print(
        f"Recording {len(cases)} {tier} cases; conservative uncached plan={planned}, "
        f"hard cap={MAX_RECORDING_SEARCHES}."
    )
    remaining = min(await real_serpapi_remaining(), await local_serpapi_remaining())
    if remaining < MAX_RECORDING_SEARCHES:
        raise RuntimeError(
            f"Recording requires the full {MAX_RECORDING_SEARCHES}-search safety margin; "
            f"SerpAPI reports only {remaining} remaining"
        )
    os.environ["EVALS_TOOL_MODE"] = "record"
    os.environ["EVALS_LLM_MODE"] = "record"
    event_root = Path(__file__).resolve().parent / "fixtures" / "events"
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']}")
        await run_case(case, artifact_path=event_root / f"{case['id']}.json")
    print(f"Recorded {_searches_used} SerpAPI searches (cap {MAX_RECORDING_SEARCHES}).")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", choices=("offline", "live"), default="offline")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    cases = load_cases(args.tier)
    if args.limit:
        cases = cases[: args.limit]
    if args.plan:
        print(
            f"{len(cases)} cases; conservative uncached search plan "
            f"{conservative_search_plan(cases)}; enforced cap {MAX_RECORDING_SEARCHES}."
        )
        return
    asyncio.run(record(args.tier, args.limit))


if __name__ == "__main__":
    # ``python -m evals.record`` otherwise gives tool imports a second module
    # instance with a different quota counter.
    import sys

    sys.modules["evals.record"] = sys.modules[__name__]
    main()
