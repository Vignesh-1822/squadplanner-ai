"""Agreement between the human rater and the LLM judge (O8 steps 6-7).

Runs with no network, no database and no API key: it reads the committed human
labels and the committed judge verdicts. Before either exists it exits 0 with a
status line, because this command is part of the success criteria and must be
runnable at every stage of the phase.

The headline statistic is quadratic-weighted Cohen's kappa. The scale is ordinal,
so plain kappa would treat a 1-vs-2 disagreement as identical to a 1-vs-5.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from evals.calibration import load_labels, load_manifest
from evals.judge import judge_outputs_path
from evals.rubrics import RUBRIC_FILES, rubric_version

SCALE = (1, 5)
_BANDS = (
    (0.20, "slight"),
    (0.40, "fair"),
    (0.60, "moderate"),
    (0.80, "substantial"),
    (1.01, "almost perfect"),
)


def band(kappa: float) -> str:
    """Landis-Koch interpretation band for a kappa value."""
    if kappa < 0:
        return "worse than chance"
    for ceiling, name in _BANDS:
        if kappa <= ceiling:
            return name
    return "almost perfect"


def quadratic_weighted_kappa(first: list[int], second: list[int]) -> dict[str, Any]:
    """Quadratic-weighted Cohen's kappa, with explicit handling of degenerate input.

    When either rater used a single score for every item their marginal distribution
    is a point mass, expected disagreement collapses onto the observed disagreement,
    and the statistic carries no information about the other rater. Reporting the
    resulting 0.0 as if it were a measurement would be misleading, so the degeneracy
    is returned alongside the number.
    """
    low, high = SCALE
    size = high - low + 1
    observed = np.zeros((size, size), dtype=float)
    for human_score, other_score in zip(first, second):
        observed[human_score - low][other_score - low] += 1.0
    total = observed.sum()
    if total == 0:
        return {"kappa": None, "degenerate": True, "reason": "no paired ratings"}
    observed /= total

    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0))
    index = np.arange(size)
    weights = ((index[:, None] - index[None, :]) ** 2) / float((size - 1) ** 2)

    denominator = float((weights * expected).sum())
    if denominator == 0.0:
        return {
            "kappa": None,
            "degenerate": True,
            "reason": "both raters gave every item the same score",
        }

    kappa = 1.0 - float((weights * observed).sum()) / denominator
    constant_first = len(set(first)) == 1
    constant_second = len(set(second)) == 1
    if constant_first or constant_second:
        who = "human" if constant_first else "judge"
        return {
            "kappa": round(kappa, 4),
            "degenerate": True,
            "reason": f"{who} scores are constant, so kappa cannot exceed 0 whatever the other rater does",
        }
    return {"kappa": round(kappa, 4), "degenerate": False, "reason": None}


def _pairs(labels: list[dict[str, Any]], pass_index: int) -> dict[str, dict[str, int]]:
    """Map item id -> criterion -> score for one labelling pass."""
    out: dict[str, dict[str, int]] = {}
    for label in labels:
        if int(label.get("pass_index", 0)) != pass_index:
            continue
        out[str(label["item_id"])] = {
            name: int(rating["score"]) for name, rating in label.get("ratings", {}).items()
        }
    return out


def _agreement(human: list[int], other: list[int]) -> dict[str, Any]:
    exact = sum(1 for a, b in zip(human, other) if a == b)
    adjacent = sum(1 for a, b in zip(human, other) if abs(a - b) <= 1)
    count = len(human)
    result = {
        "n": count,
        "exact_agreement": round(exact / count, 4) if count else None,
        "adjacent_agreement": round(adjacent / count, 4) if count else None,
        "mean_human": round(float(np.mean(human)), 3) if count else None,
        "mean_other": round(float(np.mean(other)), 3) if count else None,
        "human_distribution": {str(v): human.count(v) for v in sorted(set(human))},
        "other_distribution": {str(v): other.count(v) for v in sorted(set(other))},
    }
    if count:
        result["bias"] = round(float(np.mean(other) - np.mean(human)), 3)
    result.update(quadratic_weighted_kappa(human, other))
    return result


def compute() -> dict[str, Any]:
    """Return the full calibration result, or a status dict when inputs are missing."""
    labels_data = load_labels()
    labels = labels_data.get("labels") or []
    if not labels:
        return {"status": "awaiting_human_labels"}

    manifest = load_manifest()
    first_pass = _pairs(labels, 1)
    second_pass = _pairs(labels, 2)

    result: dict[str, Any] = {
        "status": "ok",
        "rubric_version": labels_data.get("rubric_version"),
        "rubric_version_current": rubric_version(),
        "item_count": manifest.get("item_count", len(first_pass)),
        "first_pass_labelled": len(first_pass),
        "second_pass_labelled": len(second_pass),
        "intra_rater": {},
        "judge": None,
    }
    result["rubric_drift"] = result["rubric_version"] not in (None, result["rubric_version_current"])

    # Intra-rater consistency: the ceiling on any judge's measurable agreement.
    repeated = sorted(set(first_pass) & set(second_pass))
    for criterion in RUBRIC_FILES:
        pass_one = [first_pass[item][criterion] for item in repeated if criterion in first_pass[item]]
        pass_two = [second_pass[item][criterion] for item in repeated if criterion in second_pass[item]]
        if pass_one and len(pass_one) == len(pass_two):
            result["intra_rater"][criterion] = _agreement(pass_one, pass_two)

    judge_path = judge_outputs_path()
    if not judge_path.is_file():
        result["status"] = "awaiting_judge_run"
        return result

    judge_data = json.loads(judge_path.read_text(encoding="utf-8"))
    verdicts = judge_data.get("verdicts", {})
    per_criterion: dict[str, Any] = {}
    for criterion in RUBRIC_FILES:
        human_scores: list[int] = []
        judge_scores: list[int] = []
        for item_id, ratings in sorted(first_pass.items()):
            verdict = verdicts.get(item_id, {}).get(criterion)
            if verdict is None or criterion not in ratings:
                continue
            human_scores.append(ratings[criterion])
            judge_scores.append(int(verdict["score"]))
        if human_scores:
            per_criterion[criterion] = _agreement(human_scores, judge_scores)

    result["judge"] = {
        "model": judge_data.get("model"),
        "rubric_version": judge_data.get("rubric_version"),
        "judged_at": judge_data.get("generated_at"),
        "criteria": per_criterion,
    }
    return result


def _format_criterion(name: str, stats: dict[str, Any], *, label: str) -> list[str]:
    lines = [f"  {name}"]
    kappa = stats.get("kappa")
    if kappa is None:
        lines.append(f"    quadratic-weighted kappa: undefined — {stats['reason']}")
    elif stats.get("degenerate"):
        lines.append(f"    quadratic-weighted kappa: {kappa:.3f} — UNINFORMATIVE: {stats['reason']}")
    else:
        lines.append(f"    quadratic-weighted kappa: {kappa:.3f} ({band(kappa)})")
    lines.append(
        f"    exact {stats['exact_agreement']:.0%} · within 1 {stats['adjacent_agreement']:.0%} "
        f"· n={stats['n']}"
    )
    lines.append(
        f"    mean human {stats['mean_human']} vs {label} {stats['mean_other']} "
        f"(bias {stats['bias']:+.3f})"
    )
    lines.append(f"    human {stats['human_distribution']} · {label} {stats['other_distribution']}")
    return lines


def render(result: dict[str, Any]) -> str:
    if result.get("status") == "awaiting_human_labels":
        return "awaiting human labels"

    lines = [
        "SquadPlanner judge calibration",
        f"Rubric version: {str(result['rubric_version'])[:12]}",
        f"Human labels: pass 1 {result['first_pass_labelled']}/{result['item_count']}; "
        f"consistency pass {result['second_pass_labelled']}/3.",
    ]
    if result.get("rubric_drift"):
        lines.append(
            "WARNING: rubrics have changed since these labels were recorded; "
            "the comparison below measures rubric drift, not judge accuracy."
        )

    if result["intra_rater"]:
        lines.append("")
        lines.append("Intra-rater consistency (human pass 1 vs pass 2) — the ceiling on any judge:")
        for name, stats in result["intra_rater"].items():
            lines.extend(_format_criterion(name, stats, label="repeat"))
        lines.append(
            "  NOTE: n=3 by design. Too small for a reliable kappa; read the agreement "
            "percentages, not the coefficient."
        )

    if result.get("status") == "awaiting_judge_run":
        lines.append("")
        lines.append("Awaiting judge run: python -m evals.judge")
        return "\n".join(lines)

    judge = result["judge"]
    lines.append("")
    lines.append(f"Judge vs human — {judge['model']}, scored independently per criterion:")
    for name, stats in judge["criteria"].items():
        lines.extend(_format_criterion(name, stats, label="judge"))
    lines.append("")
    lines.append(
        "Bias is mean(judge) - mean(human). A positive value is consistent with the "
        "documented self-preference of same-family judges."
    )
    lines.append(
        "Bands: <=0.20 slight, 0.21-0.40 fair, 0.41-0.60 moderate, 0.61-0.80 substantial, "
        ">0.80 almost perfect. The published cautionary case sat at 0.31."
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit the raw result instead")
    args = parser.parse_args()
    result = compute()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(render(result))


if __name__ == "__main__":
    main()
