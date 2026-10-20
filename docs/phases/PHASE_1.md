# Phase 1 — Make It Measurable

**Branch:** `phase-1-evals` · **Implementer:** Cursor · **Reviewer:** Codex
**Depends on:** Phase 0 (merged) · **Blocks:** every later phase's ability to prove it worked

> **Revision 2 — 2026-09-06.** Corrected against the codebase before implementation began. Every
> change is listed in "Corrections applied" at the end of this document, with the evidence that
> prompted it. Revision 1 was never committed to git, so there is no diff to read — the
> corrections list is the record of what changed.

---

## Why this phase exists

There is currently no way to tell whether a change to this system made it better or worse. No token
accounting exists anywhere in the codebase. `LANGCHAIN_TRACING_V2` is `false`. There is no golden
dataset, no scorer, and no baseline.

That means Phase 3 (RAG) and Phase 4 (multi-agent) could be built and shipped with no evidence they
improved anything. Phase 1 exists so that every later claim is a measured number rather than an
impression.

**Critical constraint: this phase changes no behaviour.** It does not improve prompts, swap models,
or tune the graph. It measures the system exactly as it is today and commits that as the baseline.
An "improvement" made during this phase silently destroys the baseline it exists to establish.

If a real defect is found, it goes in `docs/KNOWN_ISSUES.md` and is left in place. One already has
(see K-001 below).

---

## Verified environment facts

Measured on 2026-09-06, before planning. These supersede any assumption in revision 1.

**Credentials — all live. Nothing needs rotating.** The D-010 rotation worked.

- SerpAPI: Free Plan, **250 searches/month, 0 used this month**. `SERPAPI_MONTHLY_HARD_LIMIT` is
  `200`, so there is a deliberate 50-search margin between the app's guard and the real ceiling.
  The app's own counter in `api_usage` is a separate number it maintains itself; the pre-flight
  guard for live runs must read the **real** figure from SerpAPI's account endpoint, which costs
  zero searches, not just the local counter.
- Anthropic: `claude-haiku-4-5` and `claude-sonnet-5` both present, so D-013 is implementable.
- Google Places, Google Routes, Open-Meteo, LangSmith, MongoDB: all reachable.

**The three committed artifacts in `tests/artifacts/` are not usable as fixtures.** All three have
`is_estimated: true` on every flight and on the hotel — SerpAPI was degrading to the placeholder
branch when they were recorded, almost certainly on the pre-rotation key or an exhausted April
quota. Their Google Places data is real. See trap "recording the fallback" below.

**Those same three artifacts are the justification for the offline tier.** They are three runs of
one identical case (3 members, 3 days, Surfside Beach), and they diverged:

| Run | Wall clock | Feasibility swaps | Itinerary rebuilds | Validation outcome |
|---|---|---|---|---|
| `b64b3228` | 54.1 s | 2 | 1 | passed |
| `64faa178` | 94.5 s | 2 | 1 | passed |
| `65d48b56` | 122.1 s | 2 | **3 (bound exhausted)** | **never passed — shipped with 3 issues** |

No code changed between them. O6 asks for a scorer asserting "the itinerary rebuild loop terminated
rather than exhausting its bound"; on live data that scorer is a coin flip. This is the property the
offline tier exists to remove.

**Cost and duration of a live case.** A 3-member, 3-day trip costs 4 SerpAPI searches (one flight
per member, one hotel) and ran in 54–122 s. An 8-member case costs 9 searches. Five live cases are
roughly 20–25 searches, giving about 8 full live runs per month inside the 200 guard.

**Existing suite:** 47 tests pass with no network and no database (`motor` connects lazily, so
`test_graph_wiring.py` does not need Mongo despite constructing a checkpointer).

**Libraries:** `langchain-core` 1.6.1, `langgraph` 1.2.11, `numpy` 2.4.6. **No `scipy`, no
`scikit-learn`** — the weighted kappa in O8 is hand-rolled rather than a new dependency.

---

## Objectives

### O1 · Run the graph offline, unattended, for $0
This is the foundation everything else sits on.

**Two independent mode switches, not one.** Tools and the LLM must be switchable separately,
because three combinations are needed:

| Combination | Used by | Cost |
|---|---|---|
| tools replayed + LLM replayed | the 30 offline cases, every commit | $0 |
| tools replayed + **LLM live** | the 20 calibration itineraries (O8 step 2, D-014) | Anthropic tokens, **zero** SerpAPI searches |
| tools live + LLM live | the 5 live cases | ~20–25 searches + tokens |

A single `EVALS_REPLAY` flag cannot express the middle row, which is the one D-014 depends on. Use
`EVALS_TOOL_MODE` and `EVALS_LLM_MODE`, each one of `off` / `replay` / `record`. Both default to
`off`, and both are added to `.env_example` and `config.py`.

- **Recorded tool responses.** A replay layer for `tools/serpapi.py`, `tools/google_places.py`,
  `tools/google_routes.py` and `tools/open_meteo.py`. Capture real responses once into fixtures,
  replay from disk under `EVALS_TOOL_MODE=replay`. The tools already have an "estimated fallback"
  branch for API failure — replay must be a deliberate third mode, not a reuse of the failure path,
  or the evals will silently measure the fallback instead of the product. Insert the replay branch
  after the `api_cache` read and **before** `check_and_increment_serpapi_budget`, so replay never
  touches Mongo or the quota.
- **The recorder must refuse to save a placeholder, with one explicit baseline exception.** Reject
  and fail loudly on an estimated hotel, an empty activity list, a non-local all-zero route, or the
  weather summary `"Weather data unavailable"`. K-002 proves production deterministically sends a
  city name where SerpAPI requires an airport code, so **flight fixtures intentionally preserve the
  current `$300`, `is_estimated: true` fallback**. Tests and reports label that exception; silently
  treating it as real data is forbidden. Without this guard the trap below arrives through a
  second door: the recorder faithfully preserves an unlabelled fallback and every scorer passes
  while measuring placeholder data.
- **Recorded tool budget: 40 SerpAPI searches, hard-capped.** The recorder counts as it goes and
  aborts at 40. Design the 30 cases to share a small pool of origin airports, destinations and date
  windows so fixtures are reused across cases. Leaves ~160 searches for live runs and normal use.
- **Recorded LLM decisions.** The same for `config.py::get_llm()`. Ad-hoc `_FakeLLM` classes already
  exist in the `__main__` blocks of `agent/nodes/output_assembler.py` and
  `agent/nodes/destination_selector.py` — promote that idea into one shared, keyed replay layer.
  Cache key must include the node and a hash of the prompt so a prompt change is a cache miss, not
  a silently stale hit. The layer must implement **both** `.ainvoke` and sync `.invoke`
  (`destination_selector.py:396` is a blocking call inside an async node) and must preserve
  `bind_tools`, which `refine_agent.py` relies on.
- **HITL auto-resolution.** `tests/test_integration.py` already does this with
  `LIVE_DESTINATION_INDEX`, and `utils/streaming.py` already resumes with `Command(resume=...)`.
  Generalise both. **A case declares a list of choices, not one choice** — the severe-budget retry
  routes back through `city_selection_hitl`, so the graph asks more than once and a resolver that
  answers once will hang. Drive from `aget_state` + `Command(resume=...)` directly; do not reuse
  the SSE polling loop or the `trips` collection.
- **An in-memory checkpointer path.** `get_compiled_graph()` is Mongo-only, and the offline gate
  must run with no database. Add a sibling `compile_eval_graph(checkpointer=...)`; leave
  `get_compiled_graph()` untouched. Compiling with no checkpointer at all (as
  `test_graph_wiring.py` does) cannot interrupt or resume and is unsuitable here.
- **The eval package must import with no keys set.** `config.py:55` runs `settings = Settings()` at
  import and six fields have no default, so `pytest evals/` and `python -m evals.calibrate` both
  die before running. Fix inside `evals/__init__.py`: attempt to import `config`, and only if it
  fails for missing settings inject placeholder values and retry. Unconditional injection is wrong
  — environment variables outrank `.env` in pydantic, so it would override the real settings and
  break the record and live paths. No production file changes.

### O2 · Turn tracing on, with redaction
LangSmith is already wired (`langsmith>=0.2.0`, `config.py::configure_langsmith()`) and switched
off. Enable it (D-011). The key is present and valid.

- Every node, tool call and LLM call traced, tagged with `trip_id`. `thread_id` is already
  `trip_id`; mirror it into metadata explicitly so it is queryable.
- **Redact member email addresses before any payload leaves the process.** Phase 0 closed the PII
  leaks; piping every member's email to a third-party SaaS would partly undo that. A single
  redaction helper applied at the tracing boundary, with a test asserting no `@` appears in a
  serialised trace payload.
- **The redaction must target known member emails from the trip, not strip every `@`.** A member's
  `preference_notes` or `group_notes` can legitimately contain an `@`. Blind stripping would mangle
  user content, and the "no `@` in payload" test would then be asserting the wrong thing. The test
  fixture must therefore use notes free of stray `@` so the assertion stays meaningful, and a
  second test must assert that a note containing `@` survives redaction intact.
- Note in passing, not to fix: `member_id` is derived from the email local part by
  `api/squad.py::_member_id_from_email`, so it is partially identifying. Out of scope — the spec
  says emails.
- Tracing must stay off by default in tests and must never be required for the app to boot.

### O3 · Token, cost and latency accounting
No token accounting exists today. Add:

- A `UsageTracker` LangChain callback handler passed through the graph config alongside the
  LangSmith tracer. **This captures four of the six LLM call sites without editing them, not all
  six.** Verified by experiment: callback inheritance via LangChain's config contextvar reaches a
  sync `.invoke` inside an async node and a nested subgraph invoked with no config, so
  `preference_constraints.py:446`, `destination_selector.py:396`, `itinerary.py:741` and
  `output_assembler.py:209` are all covered for free.
  The remaining two, `refine_agent.py:231` and `refine_agent.py:270`, are **not graph nodes** —
  `utils/refinement_streaming.py` calls them as plain functions before the graph is resumed, so
  there is no run to inherit from. Those two need the config threaded in explicitly: build it in
  `refinement_streaming.py` and pass it into `plan_refinement_agentic`. Two small edits, and the
  spec's "without editing any of them" is corrected to "without editing the four in the graph".
- Record `input_tokens`, `output_tokens`, and cache-read tokens from `usage_metadata`. Tolerate the
  field being absent — the Groq provider path and any parse failure will not populate it.
- Wall-clock duration per node, and node attribution for token cost, both taken from a **recorded
  `astream_events` stream** (see O6). One mechanism serves O3's timing, O3's attribution and O6's
  trajectory assertions.
- A single pricing module with rates and the date they were checked. Current published rates:
  `claude-haiku-4-5` $1.00/$5.00 per MTok, `claude-sonnet-5` $2.00/$10.00 per MTok; cached input
  reads bill at roughly a tenth of the input rate. The Groq path (`llama-3.1-8b-instant`) has no
  rate in this phase — record tokens, report cost as unpriced rather than as zero.
- Persist a `telemetry` sub-document on the trip: per-node tokens, cost, duration, plus trip totals.
  **Merge, do not overwrite.** A HITL pause splits one trip across two or more graph invocations,
  and a refinement adds another; each must accumulate. Write points are
  `streaming.py::_emit_completion_if_done` and the refinement equivalent.
- `GET /api/trips/{trip_id}/telemetry`, member-only, following the Phase 0 authorization pattern
  (`require_member`, authorizing by email). `test_authz.py`'s route sweep picks it up automatically.
- Render it in `backend/debug_ui/index.html`. **Not** in `frontend/`. Record the new endpoint in
  `docs/FRONTEND_CONTRACT.md`.

### O4 · The golden dataset
`backend/evals/cases/`, two tiers, and the distinction between them must be documented in the
module docstring because it is easy to misread:

| Tier | Count | Tools | LLM | Cost | When | Catches |
|---|---|---|---|---|---|---|
| **offline** | ~30 | replayed | replayed | $0 | every commit | **code** regressions — constraint logic, retry routing, day maths, scoring, wiring |
| **live** | 5 | real | real | ~20–25 SerpAPI searches + LLM | manual / PR-triggered only (D-012) | **prompt and model** regressions — actual itinerary quality |

**The offline tier does not measure itinerary quality.** Its LLM output is frozen, so it can only
tell you that you broke the code around the model. Only the live tier can tell you the plan got
worse. Say this in the README too — claiming otherwise is exactly the false confidence this phase
is meant to eliminate.

Seed cases from `tests/demo_input_cases.json` (8 cases under `cases[].payload`) and
`tests/manual_cases.json` (4 under `api_cases[].payload`, plus a `deterministic_cases` index). Both
are dicts with prose keys, so they cannot be reused directly — extract the payloads. Cover at
minimum: tight budget, wide budget spread across members, conflicting preference vectors, every
dietary restriction the validator knows, a hard "avoid" note, a relaxed-pace note, a single-member
trip, the 8-member maximum, minimum and maximum trip length, and non-overlapping availability
windows.

Three clarifications, each verified against the code:

- **"Every dietary restriction the validator knows" is four:** `vegetarian`, `vegan`, `halal`,
  `gluten_free` (`RESTRICTION_KEYWORDS`, `itinerary.py:23`). The shellfish allergy in demo case 03
  is free text in `preference_notes` and is not actionable by the validator. Do not invent
  restrictions the code cannot evaluate.
- **Trip length has two different ceilings.** `api/squad.py:34` caps a real trip at
  `MAX_TRIP_DAYS = 5`; `input_parser.py:67` accepts 2 to 14. A 14-day case exercises the graph
  beyond anything the product can produce. Write both the 2-day and the 14-day case, and label the
  14-day one in the case file as graph-only, unreachable through the squad flow.
- **Cases that trigger the severe-budget retry must expect duplicated flights** (K-001). Writing
  them to expect one set makes them fail for a reason unrelated to what they test. Record the
  duplicate as expected with a comment pointing at `docs/KNOWN_ISSUES.md`, so that when K-001 is
  fixed the case goes red and is updated deliberately.

Per-case metadata alongside the payload: `tier`, `hitl_choices` (a list), `expect_budget_retry`,
`expect_fairness_retry`, `expect_validation_rebuild`, and the expected node sequence.

### O5 · Deterministic scorers
Free, no LLM, no network. These encode the product's actual promises:

- Every member's share is within their stated budget.
- Every dietary restriction present in the group is satisfied by each day's meals.
- No activity matches a hard-avoid term from `preference_constraints`.
- Day count equals the trip window; dates are contiguous and correctly ordered.
- Every activity falls inside the destination's `search_radius_km`.
- Consecutive activities within a day are geographically plausible.
- Day 1 starts after arrival and the final day ends before departure.
- Output schema is complete: `days`, `trip_pitch`, `constraint_satisfaction`, fairness scores.

Two of these describe promises the code does not currently make. Both are reported as-is; neither
is "fixed" in this phase.

- **Per-member budget compliance is not checked anywhere.**
  `fairness_scorer.py::compute_fairness` computes each member's cost as a fraction of their budget
  and then tests only whether `max - min <= 0.30`. Every member can be at 150% of budget and
  `fairness_passed` is still `True`. **Report both numbers:** the literal promise ("is any member
  over their own stated budget?") as the headline, and the code's own utilisation spread beside it.
  Expect the headline to show failures in the baseline. That gap is the measurement, not a bug to
  close here.
- **`search_radius_km` never reaches the trip state.** It exists in `data/destinations.json`, but
  `destination_selector.py:412` copies only `id`, `name`, `state`, `type`, `score`, `coords`,
  `llm_reasoning`, `cost_level` and `nearest_airports` into a candidate. Separately,
  `google_places.py` queries a hardcoded `radius: 20000.0` regardless of the data file. The scorer
  must therefore join back to `destinations.json` by id, and the report must note that the fetch
  radius and the scored radius are different numbers.

### O6 · Trajectory scorers
Also free. Assert the process, not just the result:

- The expected node sequence ran for the case.
- The budget-pressure retry fired when, and only when, the case is designed to trigger it.
- The fairness retry likewise.
- The itinerary rebuild loop terminated rather than exhausting its bound.
- Tool call arguments were well-formed (dates ISO, coords numeric, categories from the known set).

**Read these from a recorded `astream_events` stream, not from `get_state_history` alone.** The
itinerary subgraph is invoked as a plain async call (`itinerary.py:1168`), is compiled without a
checkpointer, and `run_itinerary_node` merges back only `days`, `constraint_satisfaction` and
`decision_log` — so `validation_rebuild_count` and `feasibility_swap_count` are discarded and are
invisible to the orchestrator's state history. The rebuild-bound assertion cannot be written the
way revision 1 described.

Subgraph events do surface in the parent event stream — `NODE_PROGRESS_MAP` in `streaming.py`
already contains `build_itinerary` and `validation_gate` and the SSE code reports progress for
them. So the harness records one event artifact per case, and that single artifact yields the node
sequence including subgraph steps, the rebuild count (how many times `build_itinerary` appears),
per-node timings for O3, and the node active at each LLM call for O3's cost attribution.

Bounds to assert, for case design: `destination_retry_count >= 3` forces the budget loop to give up
and proceed even while still severe; `hotel_retry_count < 2` bounds the fairness retry;
`validation_rebuild_count < 2` bounds the rebuild; `feasibility_swap_count >= 2` stops the swap
loop. Note that `destination_retry_count` increments on the **first** `select_destination` run too,
so a first pass leaves it at 1, not 0.

### O7 · LLM-as-judge — live tier only
Judged by `claude-sonnet-5` (D-013), which is stronger than the `claude-haiku-4-5` planner.

Three rubrics, written out explicitly and version-controlled as prompt files, each scoring one
criterion separately: **itinerary coherence**, **fairness across members**, **trip-pitch quality**.
Judge output must be structured (score plus written justification), and the justification is stored
so a disagreement can be inspected.

Running the judge against the offline tier is pointless — the output is frozen, so the score never
moves. Wire it to the live tier only.

### O8 · Validate the judge before trusting it (D-014)
The planner and the judge are both Claude models. Same-family judging carries documented
self-preference bias; one published case reached only 0.31 Cohen's kappa against domain experts
while looking like a working metric.

The response is to measure it, not to hand-wave it.

**This objective contains a mandatory human handoff.** Sequence it exactly as follows — it depends
on O1 and blocks the final part of O7:

1. **Write the rubrics first** (shared with O7), each on a **1-5 ordinal scale with written anchors
   describing what each level means for this product** — not adjectives. "A 4 has at most one
   activity a member's budget cannot absorb" is an anchor; "good fairness" is not. Vague anchors are
   the usual reason calibration produces an uninterpretable number.
2. **Harvest 20 itineraries from the 30 Session 1 recordings.** Those recordings contain genuine
   live planner output captured during the record run; rebuilding them with both eval modes set to
   `replay` spends $0 and makes no network calls. Exact tool replay plus a fresh planner cannot work:
   `find_place_by_text` queries and `get_route` coordinates are derived from the generated schedule,
   so a fresh schedule produces unrecorded request keys and fails strict replay. Stratify the 20
   across budget spread, group size, dietary load and trip length, and use deterministic-scorer
   results as a quality proxy so clean, mixed and degraded output are all represented. Store those
   verdicts only in the manifest; the labelling payload must not contain them. Commit as fixtures.
3. **Build a labelling page in `backend/debug_ui/`** — one itinerary at a time, rendered readably
   (days, activities, per-member costs), rubric shown alongside, radio buttons per criterion,
   progress saved to a JSON file so the session can be interrupted and resumed.
   **The page must never display the judge's score, or any model-generated suggestion, before a
   label is committed.** Anchoring the human rater invalidates the entire measurement.
   `debug_ui/` is served as static files, so the page cannot write to disk on its own. It needs two
   small admin-authenticated routes — one to load progress, one to save a label — writing under
   `backend/evals/calibration/`. `require_member` cannot protect a non-trip resource because it
   requires a `trip_id`; admin access also prevents arbitrary registered users from writing ground
   truth into the repository. No Mongo; a JSON file on disk keeps the calibration step runnable in
   CI. The page must also show per-member totals, which the existing debug renderer does not show
   today.
4. **STOP HERE AND HAND OFF TO MANOJ.** The labelling is human judgement and is the whole point of
   the exercise; an agent must not produce, suggest, or pre-fill labels. Do not proceed past this
   step. Roughly three hours of human work, resumable.
   **The judge has not run at this point and no judge output exists anywhere in the repository.**
   Revision 1 left the timing open; running the judge only after the labels are committed removes
   any possibility of leakage into the labelling surface, and costs nothing to defer.
5. Manoj re-labels the first three items blind at the end as an **intra-rater consistency check**.
   Stored as a separate pass on the same item rather than overwriting the first label, so both are
   available to the calibration. If his own agreement with himself is weak, the rubric is too vague
   and must be rewritten before any judge number is meaningful.
6. **`python -m evals.calibrate`** computes agreement between judge and human, per rubric, from the
   committed labels and stored judge outputs, with **no LLM call**, so it runs in CI. Because the
   scale is ordinal, report **quadratic-weighted Cohen's kappa** as the headline — plain kappa
   treats a 1-vs-2 disagreement as identical to 1-vs-5 — plus exact-agreement percentage for
   interpretability, and the intra-rater kappa from step 5 as the ceiling. Hand-rolled on `numpy`;
   `scipy` and `scikit-learn` are not installed and are not worth adding for this.
   Before labels exist the command must **exit 0 and print "awaiting human labels"**, not fail — it
   is listed in the success criteria and must be runnable at every stage.
7. The figures and the known bias caveats (position, verbosity, self-preference, format) go in the
   README next to any judge score. Use the standard interpretation bands so the number is readable:
   below 0.20 slight, 0.21-0.40 fair, 0.41-0.60 moderate, 0.61-0.80 substantial, above 0.80 almost
   perfect. The published cautionary case sat at 0.31 - "fair", and not trustworthy.
- Recompute whenever the judge model or a rubric changes.

### O9 · Reporting and the committed baseline
- `python -m evals.report` prints a scorecard: per-scorer pass rate, cost per trip, p50/p95 node
  latency, judge scores with kappa alongside.
- Every offline number in the scorecard is labelled as such. The report must state plainly that
  offline results cannot speak to itinerary quality.
- **The report prints a "live run needed" line** listing any case whose LLM replay key missed
  because its prompt changed. That is the signal to spend quota, and it makes the decision
  tool-prompted rather than remembered.
- The first full run is committed as `backend/evals/baseline.json`. Every later phase compares
  against it. Like `calibrate`, `report --baseline` must exit 0 with a clear message before the
  baseline file exists.

---

## When to run the live tier

The offline tier is blind to exactly three things: prompt text, model choice, and what gets fed
into a prompt. Everything else it covers, and covers better than the live tier, because a failure
is attributable to the change that caused it.

Run live when:

- a prompt was edited, a model was swapped, or a node's prompt inputs changed (Phase 3's retrieval
  and Phase 4's routing both qualify);
- `evals.report` prints a "live run needed" line;
- a phase is about to close — **once per phase boundary regardless of what changed**, because
  fixtures age. A closed venue or a changed response format leaves the offline suite green forever
  while production breaks, which is the April failure in reverse.

Do not run live to check a refactor, a new node, changed routing, constraint logic, or date maths.
That is what the offline tier is for, and at ~8 live runs per month the quota does not survive
casual use.

---

## Out of scope

- **Improving anything.** No prompt edits, no model routing, no graph changes. Phase 1 measures the
  system as-is. Model routing and prompt caching are Phase 4.
- **Fixing K-001** or anything else found along the way. Findings go in `docs/KNOWN_ISSUES.md`.
- Anthropic Batch API (D-015).
- GitHub Actions / nightly automation — Phase 8.
- Langfuse (D-011 chose LangSmith).
- Any change under `frontend/`.

---

## Success criteria

Split into two gates, because O8 step 4 mandates a stop in the middle and revision 1's single gate
was unsatisfiable: two of its four commands depend on labels that do not exist until Manoj produces
them.

### Gate A — end of session 2, before the handoff

From `backend/`, with **no network, no MongoDB, and no API keys set**:

```bash
# 1 — the offline gate: ~30 cases, deterministic + trajectory scorers
./venv/bin/python -m pytest evals/ -q

# 2 — Phase 0 and existing suites still green
./venv/bin/python -m pytest tests/ -q --ignore=tests/test_integration.py

# 3 — wiring smoke check
./venv/bin/python -c "import main; print('ok')"

# 4 — calibration and report run cleanly with no data yet
./venv/bin/python -m evals.calibrate --report   # prints "awaiting human labels", exits 0
./venv/bin/python -m evals.report               # offline scorecard, no baseline required
```

Plus, by inspection: the labelling page renders item 1 of 20, and `grep` finds no judge output
anywhere in the repository.

### Gate B — end of session 3, after the labels are committed

```bash
# 5 — judge calibration reports Cohen's kappa from committed labels, no LLM call
./venv/bin/python -m evals.calibrate --report

# 6 — scorecard renders from the committed baseline
./venv/bin/python -m evals.report --baseline
```

The live tier is invoked separately and is expected to cost money:

```bash
RUN_LIVE_EVALS=true ./venv/bin/python -m evals.run --live
```

It must refuse to start if the remaining SerpAPI monthly budget is below what the run needs. Read
the real remaining count from SerpAPI's account endpoint (zero searches) as well as the local
`api_usage` counter, and refuse on the lower of the two.

---

## Sessions

Three plan-and-build sessions. Each ends at a committable, reviewable state. The stop between 2 and
3 is mandatory and is not an agent decision.

| # | Scope | Objectives | Gate |
|---|---|---|---|
| **1** | Offline replay for four tools and the LLM, event recording, in-memory checkpointer, HITL auto-resolution, tracing with redaction, token/cost/latency accounting, telemetry endpoint and debug panel, the 30 offline cases, deterministic scorers, trajectory scorers | O1–O6 | Gate A commands 1–3, plus a per-node cost and latency table from an offline run |
| **2** | Three rubrics with anchors, 20 calibration itineraries, labelling page and its two routes | O7 rubrics, O8 steps 1–3 | Gate A command 4 and the inspection checks. **Then STOP.** |
| **3** | Judge run against the live tier and the 20, calibration maths, scorecard, committed baseline, README with bias caveats | O7 rest, O8 steps 5–7, O9 | Gate B |

---

## Known traps

- **Replay must not be the fallback path.** `tools/*` already degrade to estimated results when an
  API errors. If replay is implemented by triggering that branch, every eval measures the fallback
  rather than the product, and all scorers will pass while telling you nothing.
- **Recording the fallback is the same trap through a second door.** All three existing artifacts
  carry `is_estimated: true`. If the recorder runs while a tool is degrading, it writes placeholder
  data into the fixtures permanently. Hence the recorder guard and the committed fixture assertion
  in O1.
- **A frozen-LLM eval cannot detect a worse prompt.** Keep the two tiers clearly labelled in code
  and in the report output, or the numbers will be over-read.
- **The LLM replay key must include a prompt hash.** Otherwise editing a prompt silently replays the
  old response and the suite reports success on a change it never executed.
- **One mode switch is not enough.** D-014's 20 itineraries need replayed tools with a live LLM.
- **`get_current_user` returns no `_id`** (it is projected out). The telemetry endpoint must
  authorize by email, as the Phase 0 dependencies do.
- **The 200/month SerpAPI ceiling is the binding constraint**, not token cost. Anything that runs
  real searches needs a guard. The real ceiling is 250; the 200 is the app's own margin.
- **Tracing must never become a hard dependency** — the app has to boot and the tests have to pass
  with `LANGCHAIN_TRACING_V2=false` and no API key present.
- **The eval package must import with no keys.** `config.py:55` fails on six required fields.
- **The severe-budget retry re-enters the HITL pause.** A resolver that answers once will hang.
- **The itinerary subgraph's counters never reach the orchestrator.** Use the event stream.
- **Telemetry must merge across graph invocations.** HITL splits one trip into two or more runs.

---

## Known issues found while specifying this phase

Recorded here and in `docs/KNOWN_ISSUES.md`. **Not fixed in this phase** — Phase 1 measures the
system as it is.

### K-001 · The severe-budget retry duplicates flights and activities

`state.py:99` declares `flights: Annotated[list[FlightResult], operator.add]` and line 100 does the
same for `activities`. When `route_after_budget` returns `"severe"` the graph loops back to
`select_destination`, through `city_selection_hitl` a second time, and re-runs
`parallel_data_fetch`. Neither `select_destination` nor `dynamic_tool_selection` clears the previous
lists, so the appended results accumulate: after one retry the trip carries two full sets of
flights, one for the abandoned destination and one for the new one.

Downstream, `budget_analyzer`, `compute_fairness` (via `_cheapest_member_flight`, which takes the
`min` across both sets) and the itinerary subgraph all run over the duplicated data. Candidate for
Phase 2. Offline cases that trigger this path record the duplicate as expected behaviour.

---

## Corrections applied in revision 2

Each item was verified against the code before being written here.

1. **Credentials.** Revision 1 predated the D-010 rotation being confirmed. All seven services are
   live; SerpAPI has 250/month with 0 used. Added as "Verified environment facts".
2. **The success criteria were unsatisfiable.** Commands 3 and 4 needed human labels and a
   committed baseline, yet sat alongside pre-handoff commands under one environment banner. Split
   into Gate A and Gate B, and `calibrate`/`report` must now exit 0 with a message before data
   exists.
3. **The eval package could not import with no API keys**, contradicting the stated environment.
   `config.py:55` has six required fields. Fix scoped to `evals/__init__.py`.
4. **One mode switch could not express D-014's combination** of replayed tools with a live LLM.
   Replaced `EVALS_REPLAY` with `EVALS_TOOL_MODE` and `EVALS_LLM_MODE`.
5. **"All six LLM call sites without editing any of them" was four of six.** Verified by
   experiment that callback inheritance covers the four in-graph sites including the sync call and
   the nested subgraph; the two `refine_agent.py` sites run outside the graph and need the config
   passed explicitly.
6. **The rebuild-bound assertion could not be read from `get_state_history`.**
   `run_itinerary_node` discards the subgraph's counters. Replaced with a recorded
   `astream_events` artifact, which also supplies O3's timings and cost attribution.
7. **A real defect was found and left in place** — K-001 above. Offline cases on that path expect
   the current behaviour so they fail for the right reasons.
8. **`search_radius_km` is not in the trip state** and the Places fetch radius is hardcoded to
   20 km. The scorer joins `destinations.json`; the report notes the two radii differ.
9. **Per-member budget compliance is not checked by the code.** Report both the literal promise and
   the code's utilisation spread; expect red in the baseline.
10. **"Every dietary restriction the validator knows" is four**, not an open set.
11. **Trip length has two ceilings** — 5 through the squad flow, 2–14 through the graph. Both
    extremes are written; the 14-day case is labelled graph-only.
12. **The labelling page cannot persist by itself** — `debug_ui/` is static. Two routes added.
13. **Judge timing pinned to after the labels**, removing any leakage path into the labelling page.
14. **Weighted kappa is hand-rolled** — no `scipy` or `scikit-learn` installed.
15. **The PII test needed sharpening.** Blind `@` stripping would corrupt user notes; redaction
    targets known member emails, with a second test asserting a note containing `@` survives.
16. **Telemetry must merge, not overwrite**, because HITL splits a trip across invocations.
17. **Added a "when to run the live tier" policy**, since at ~8 runs per month the tier cannot
    absorb casual use, and added the "live run needed" report line so the tooling prompts it.
18. **Recording budget capped at 40 SerpAPI searches**, enforced by a counter in the recorder.
19. **The offline tier's justification is now evidence-based** — three identical runs in
    `tests/artifacts/` diverged, one exhausting the rebuild bound, which is exactly the O6 assertion
    that live-only testing cannot make reliably.
20. **Three sessions** replace the implicit single unit, with the mandatory stop between 2 and 3.

## Corrections applied in revision 3

21. **Fresh planner output cannot use exact tool replay.** The planner authors meal-place query text
    and chooses route stops, so live LLM output changes `find_place_by_text` and `get_route` request
    keys. Session 2 harvests 20 genuine live-model outputs already captured by Session 1 instead,
    rerunning them with both modes on replay for $0. Selection is stratified by both required input
    dimensions and deterministic-score quality bands.
22. **Calibration routes are admin-authenticated, not member-authenticated.** `require_member`
    requires a trip ID, while calibration is not a trip. Restricting the file-writing routes to an
    administrator also prevents any registered account from modifying human ground truth.
23. **K-002 remains a deliberate Phase 1 baseline defect.** Fixing the city-to-airport mapping would
    change member budgets, retry trajectories and most recorded fixtures. The 20 calibration items
    remain valid after that later fix because they are frozen historical outputs; their fairness
    rubric labels the fixed $300 flight estimate and does not reward its realism.
