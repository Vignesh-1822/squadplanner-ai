# SquadPlanner Evaluations

## Read this before interpreting a score

The **offline** tier replays frozen tool responses and frozen LLM output. It
catches code regressions in routing, constraints, date arithmetic, scoring,
schema and wiring. It **does not measure itinerary quality** and cannot prove a
prompt or model improved.

The **live** tier calls real tools and models. Only it measures prompt/model
quality. It is manually gated because each five-case run spends roughly 20–25
of the application's 200-search monthly SerpAPI budget.

Run live after a prompt, model or prompt-input change, when the report identifies
a prompt replay miss, and once at each phase boundary to detect stale fixtures.

## Commands

From `backend/`:

```bash
./venv/bin/python -m pytest evals/ -q
./venv/bin/python -m evals.run
./venv/bin/python -m evals.report
RUN_LIVE_EVALS=true ./venv/bin/python -m evals.run --live
```

Tool and LLM controls are independent:

- `EVALS_TOOL_MODE=off|record|replay`
- `EVALS_LLM_MODE=off|record|replay`

This independence supports mixed diagnostic runs, but exact tool replay cannot
be combined with a fresh planner output for calibration. Meal-place queries and
route coordinates are derived from the planner's generated schedule, so a new
schedule produces new request keys and strict replay misses.

## Human calibration handoff

The 20 calibration itineraries in `evals/calibration/itineraries/` are harvested
from the 30 Session 1 recordings. Those recordings contain genuine live planner
output captured during the fixture run; rebuilding the calibration set simply
replays that output for $0 and makes no network calls:

```bash
./venv/bin/python -m evals.calibration.build
```

Selection is stratified across group size, trip length, dietary load and budget
spread, and also across clean, mixed and degraded deterministic-score bands.
The score-band metadata stays in `manifest.json` and is never returned by the
labelling API.

The labelling page is `/debug/label.html`. It requires an account with
`is_admin: true`; registration intentionally defaults that field to false.
Label pass 1 contains all 20 items. After a break, `/debug/label.html?pass=2`
blindly re-labels the first three items for the intra-rater consistency check.
Progress is saved after every item in `evals/calibration/labels.json`.

The page and its GET API never receive saved ratings, deterministic verdicts or
automated suggestions. Do not add any such value to the item payload. The judge
did not run until the human labels were complete and committed, and
`evals/judge.py` refuses to start while `labels.json` is missing.

## Current-baseline caveat

K-002 in `docs/KNOWN_ISSUES.md` means production flight searches currently
degrade to estimated data. Flight fixtures intentionally preserve and clearly
label that current behaviour. The calibration page therefore shows the same
fixed $300 estimate for every member and does not render the raw flight list,
which can also contain abandoned-destination entries because of K-001. Other
fallback responses are rejected by the recorder.


## Judge calibration results

Run `./venv/bin/python -m evals.calibrate --report`. The numbers below are the
committed baseline: 20 items, human labels from a single rater, judged by
`claude-sonnet-5` with each criterion scored in a separate call.

| Criterion | Quadratic-weighted kappa | Exact | Within 1 | Bias |
|---|---|---|---|---|
| Fairness across members | **0.449** — moderate | 40% | 80% | −0.65 |
| Itinerary coherence | **−0.071** — worse than chance | 40% | 80% | +0.50 |
| Trip-pitch quality | undefined — see below | 0% | 45% | **+1.55** |

Bias is `mean(judge) − mean(human)`. Bands: ≤0.20 slight, 0.21–0.40 fair,
0.41–0.60 moderate, 0.61–0.80 substantial, >0.80 almost perfect. The published
cautionary case that motivated D-014 sat at 0.31.

**The judge is not trustworthy as a standalone quality metric.** Only fairness
reaches moderate agreement. Coherence is no better than chance: the judge never
reproduces the rater's harshest scores, giving 1 twice where the human gave it
eight times. Trip-pitch quality is the clearest failure — the judge rated the
planner's own prose 4 or 5 on every single item the human scored 3, a systematic
+1.55 gap and zero exact agreement. That is the documented same-family
self-preference effect, visible directly in the data D-014 was written to catch.

### Why one kappa is undefined

Quadratic-weighted kappa is `(observed − expected) / (1 − expected)`. When one
rater gives every item the same score their marginal distribution is a point
mass, observed and expected disagreement coincide, and the statistic collapses to
0 or 0/0 regardless of the other rater — even under perfect agreement. The human
scored trip-pitch quality 3 on all 20 items, so no judge could have produced a
meaningful coefficient. `calibrate.py` reports this as degenerate rather than
printing a 0 that reads like a measurement. The bias figure still carries signal
and is the number to read for that criterion.

### Intra-rater ceiling

The rater re-scored the first three items blind. Exact self-agreement was 5 of 9
ratings: 2/3 on coherence, 0/3 on fairness, 3/3 on pitch. **A judge cannot be
shown to agree with a rater more reliably than the rater agrees with themself**,
so the fairness figure above is bounded by rater noise as well as judge error.
`n=3` is far too small for a reliable coefficient; read the percentages.

The fairness swings are explained rather than random. On item 03 the first pass
scored 3, citing a member's stated "no early mornings" being violated; the second
pass scored 5, citing only budget headroom. Two different readings of the same
word — a rubric ambiguity, and one of the inputs to rubric v2.

### Known biases not corrected here

| Bias | Status in this measurement |
|---|---|
| Self-preference | Measured, and clearly present on trip-pitch quality (+1.55). |
| Verbosity | Not controlled. Pitch length varies 1,911–3,087 characters across the corpus. |
| Position | Partly controlled: each criterion is scored in an isolated call, so no ordering of criteria can leak. Item order within the run is fixed and not randomised. |
| Format | Not controlled. The judge receives the same JSON payload the labelling page rendered, but sees raw JSON where the human saw formatted HTML. |
| Determinism | `claude-sonnet-5` rejects a `temperature` parameter, so the run is not seeded. The verdicts are committed, so the *analysis* is reproducible; a re-run of the judge may differ. |

### What the rubrics missed

The rater consistently graded axes the rubrics do not contain: whether the trip
is *interesting* (coherence), budget under-utilization (fairness), and
presentation quality (pitch). See `docs/PRODUCT_FEEDBACK.md` F-29. Rubric v1 is
frozen as the version these labels were made against; any revision must be
written as a new version, because `labels.json` pins `rubric_version` and
`calibrate.py` refuses to compare across a change.
