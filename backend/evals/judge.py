"""LLM-as-judge over the calibration corpus (O7).

The judge is deliberately kept off the product path: it constructs its own client
rather than going through ``config.get_llm()``, so nothing here can alter how the
planner behaves. It also refuses to run before the human labels exist, which removes
any route by which a model score could anchor the rater.

Running this costs Anthropic tokens. The results are committed to
``calibration/judge_outputs.json`` so that ``evals.calibrate`` needs no network,
no database and no API key.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from evals.calibration import calibration_root, load_item, load_labels, load_manifest
from evals.rubrics import RUBRIC_FILES, rubric_version

JUDGE_MODEL = "claude-sonnet-5"
_RUBRIC_DIR = Path(__file__).resolve().parent / "rubrics"


def judge_outputs_path() -> Path:
    return calibration_root() / "judge_outputs.json"


class Verdict(BaseModel):
    """Structured judge response for one item against one rubric."""

    score: int = Field(ge=1, le=5, description="Rubric level from 1 to 5")
    justification: str = Field(description="Why this level and not the ones adjacent to it")


def _rubric_text(name: str) -> str:
    return (_RUBRIC_DIR / f"{name}.md").read_text(encoding="utf-8")


def _prompt(rubric_name: str, item: dict[str, Any]) -> str:
    """Build the judge prompt.

    The item is passed verbatim — the same JSON the labelling page rendered for the
    human rater — so judge and human are scoring identical evidence.
    """
    return (
        "You are grading one generated group-trip itinerary against one rubric.\n\n"
        "Apply the rubric exactly as written. Choose the single level whose description "
        "best matches the itinerary. Do not reward or penalise anything the rubric does "
        "not mention. If evidence for a level's condition is absent from the itinerary, "
        "treat that condition as unmet rather than assuming it holds.\n\n"
        f"=== RUBRIC ===\n{_rubric_text(rubric_name)}\n\n"
        f"=== ITINERARY ===\n{json.dumps(item, indent=2, sort_keys=True)}\n\n"
        "Return the rubric level and a justification that names the specific itinerary "
        "details behind your choice."
    )


def _client():
    """Construct the judge model directly, bypassing the product LLM factory."""
    from langchain_anthropic import ChatAnthropic

    from config import settings

    return ChatAnthropic(
        model=JUDGE_MODEL,
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
    ).with_structured_output(Verdict)


async def _score_once(model, rubric_name: str, item: dict[str, Any]) -> dict[str, Any]:
    """Score one item against one rubric, retrying transient failures.

    A call that never succeeds is recorded as an error rather than aborting the run,
    so a single bad response cannot discard the tokens already spent.
    """
    prompt = _prompt(rubric_name, item)
    last_error = ""
    for _ in range(3):
        try:
            result: Verdict = await model.ainvoke(prompt)
            return {"score": int(result.score), "justification": result.justification.strip()}
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            last_error = f"{type(exc).__name__}: {exc}"
            await asyncio.sleep(2)
    return {"score": None, "justification": None, "error": last_error}


async def run_judge(*, force: bool = False, limit: int | None = None) -> dict[str, Any]:
    """Score every calibration item against every rubric and persist the verdicts."""
    labels = load_labels()
    if not labels.get("labels"):
        raise RuntimeError(
            "Refusing to run: human labels do not exist yet. The judge must run after "
            "labelling so that no model score can anchor the rater."
        )
    output_path = judge_outputs_path()
    if output_path.is_file() and not force:
        raise RuntimeError(
            f"{output_path.name} already exists. Re-running spends tokens; pass --force to replace it."
        )

    current_version = rubric_version()
    if labels.get("rubric_version") not in (None, current_version):
        raise RuntimeError(
            "Rubrics have changed since the labels were recorded. Judging the new rubric "
            "against the old labels would measure rubric drift, not judge accuracy."
        )

    manifest = load_manifest()
    item_ids = [str(item["id"]) for item in manifest.get("items", [])]
    if limit is not None:
        item_ids = item_ids[:limit]
    model = _client()

    verdicts: dict[str, dict[str, Any]] = {}
    for item_id in item_ids:
        item = load_item(item_id)
        verdicts[item_id] = {}
        for rubric_name in RUBRIC_FILES:
            verdict = await _score_once(model, rubric_name, item)
            verdicts[item_id][rubric_name] = verdict
            print(f"  {item_id} · {rubric_name}: {verdict.get('score', 'FAILED')}")

    payload = {
        "schema_version": 1,
        "model": JUDGE_MODEL,
        "rubric_version": current_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scored_independently_per_criterion": True,
        "verdicts": verdicts,
    }
    if limit is None:
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(f"--limit {limit}: smoke run only, {output_path.name} not written")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the calibration judge (spends Anthropic tokens)")
    parser.add_argument("--force", action="store_true", help="replace existing judge outputs")
    parser.add_argument("--limit", type=int, default=None, help="smoke-test N items without writing")
    args = parser.parse_args()
    payload = asyncio.run(run_judge(force=args.force, limit=args.limit))
    scored = len(payload["verdicts"])
    failed = sum(
        1
        for item in payload["verdicts"].values()
        for verdict in item.values()
        if verdict.get("score") is None
    )
    where = "not written (smoke run)" if args.limit is not None else str(judge_outputs_path())
    print(f"Judged {scored} items × {len(RUBRIC_FILES)} rubrics; {failed} failed. Output: {where}")


if __name__ == "__main__":
    main()
