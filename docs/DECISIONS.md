# Decision Log

One entry per scoping decision made during the SOTA improvement plan. Newest last.
Rationale for the overall route lives in `docs/ROADMAP.md`.

---

### D-001 · Roll back the solo frontend attempt, keep the API contract
**Phase:** pre-0 · **2026-08-29**

Manoj's solo attempt at finishing the frontend is reverted from `main`, but
`frontend/src/services/{ApiList,index}.js` stays. Full attempt preserved on branch
`wip/solo-frontend-attempt` (cc27331) as a reference implementation.

**Why:** Vignesh owns the UI and shouldn't inherit merge conflicts, but throwing away the
service layer would orphan working backend endpoints and force him to reverse-engineer the
contract from Python. Contract documented in `docs/FRONTEND_CONTRACT.md`.

---

### D-002 · Let the deployed demo break during Phase 0
**Phase:** 0 · **2026-08-30**

`showcase/` has no authentication and calls `POST /trips`, `GET /trips/{id}`,
`POST /confirm-city` and `POST /refine` anonymously. Phase 0 will 401 all of them and the Vercel
demo will stop working. Accepted; `showcase/` is retired in Phase 7.

**Why:** Keeping the demo alive would mean building a seeded demo-user path — real work, on an app
we're deleting. Not worth it.

---

### D-003 · Refinement is leader-only
**Phase:** 0 · **2026-08-30**

`POST /trips/{id}/refine` requires the trip leader, not any member.

**Why:** It costs money and mutates shared state. Widening it is a product decision, not a security
one — revisit in Phase 7 alongside group voting. Reading the refinement stream stays member-level so
the squad can watch the update land.

---

### D-004 · Admin access via an `is_admin` flag on the user document
**Phase:** 0 · **2026-08-30**

Rather than deleting `/admin/serpapi-usage` or guarding it with a shared secret header.

**Why:** ~10 lines, and a role on the user model reads better to a reviewer than a magic header.
Gives us somewhere to hang future admin routes.

---

### D-005 · 24-hour token expiry **and** `token_version` revocation
**Phase:** 0 · **2026-08-30**

Manoj chose 24h over the recommended 7 days, keeping `token_version` as well.

**Why:** Deliberately more conservative than proposed — short expiry limits the blast radius of a
leaked token, `token_version` provides the kill switch. Cost is more frequent re-logins, accepted.
`token_version` is free to verify because `get_current_user` already loads the user document.

---

### D-006 · Move the SerpAPI quota counter to its own collection
**Phase:** 0 · **2026-08-30**

The counter (`{type: "serpapi_usage", month, calls_used}`) moves from `api_cache` to `api_usage`.

**Why:** A TTL index on `api_cache.cached_at` currently spares the counter only because that document
has no `cached_at` field. Mongo TTL ignores documents missing the indexed field — true today, but if
anyone ever adds a timestamp there the monthly spend guard silently resets to zero and we find out
via the bill. Separate collections remove the coupling entirely.

---

### D-007 · Zero frontend footprint
**Phase:** 0 · **2026-08-30**

`frontend/src/services/{ApiList,index}.js` reverted to upstream state. `frontend/` is now
byte-identical to `Vignesh-1822/squadplanner-ai@47fb381` and stays that way for every phase.
API changes are communicated by editing `docs/FRONTEND_CONTRACT.md`, never the JavaScript.

**Why:** Vignesh authored all five revisions of `ApiList.js`. Our PRs should be reviewable as pure
backend work — that is what he actually needs in order to build against them. The working
implementation is preserved on `wip/solo-frontend-attempt` as a reference.

---

### D-008 · `backend/debug_ui` is the manual test surface, not `showcase/`
**Phase:** 0 · **2026-08-30**

Re-mount `/debug` and add a login step to the existing 953-line debug runner (Phase 0, O8).

**Why:** It already exists, it lives in `backend/`, and it can never collide with Vignesh.
`showcase/` is a React app we are deleting in Phase 7 — adding a login flow to it would be work
spent on something with a scheduled end date.

---

### D-009 · Merge upstream after every phase
**Phase:** 0 · **2026-08-30**

Each phase branch opens a PR into `Vignesh-1822/squadplanner-ai` as soon as its success criteria
pass, rather than batching phases.

**Why:** `main`, `origin/main` and `upstream/main` are all at `47fb381` with zero divergence, and
Vignesh has had nothing in flight for 68 days — conflict risk is at its minimum right now and grows
with every week of held-back work. `backend/api/trips.py` in particular is a file he edits often.
Merging early also unblocks him to start the real UI against a secured API instead of waiting.

---

### D-010 · Rotate the leaked keys; do not rewrite history
**Phase:** 0 · **2026-08-30**

`backend/.env` was committed in `86c9249` (11 Apr) and removed in `96a0eff` (24 Apr). Both repos are
public, so `MONGODB_URI`, `ANTHROPIC_API_KEY`, `SERPAPI_KEY`, `GOOGLE_PLACES_API_KEY` and
`GOOGLE_ROUTES_API_KEY` are recoverable via `git log -p -- backend/.env`. All five are being rotated.
History is left as-is.

**Why:** Rotation is the fix — the exposed values are dead once rotated. Purging would require
`git-filter-repo` plus a force-push to two public repos and a re-clone by Vignesh, for no additional
security benefit. Revisit only if the repo is ever used as a portfolio showcase where a reviewer
running `git log` would matter.

---

### D-011 · LangSmith, not Langfuse
**Phase:** 1 · **2026-09-05**

Enable the existing LangSmith wiring rather than integrating Langfuse.

**Why:** `langsmith>=0.2.0` and `config.py::configure_langsmith()` are already in place — enabling
is an environment variable, where Langfuse would be a new integration plus (if self-hosted) six
containers. Langfuse has the better free tier and stronger eval tooling, but the effort is better
spent on the eval harness itself than on swapping observability vendors. Revisit if the 5k-trace
free tier or the seat-based pricing becomes a real constraint.

---

### D-012 · Two eval tiers; live runs are manual, not nightly
**Phase:** 1 · **2026-09-05**

~30 offline cases (replayed tools and LLM, $0) run on every commit. 5 live cases (real tools and
LLM) run manually or on PR only.

**Why:** SerpAPI's 200-search monthly ceiling — not token cost — is the binding constraint. Five
live trips cost roughly 20 searches per run, giving about ten full runs a month. A nightly job
would exhaust the quota in a week. Revisit when SerpAPI is no longer the ceiling.

---

### D-013 · `claude-sonnet-5` as the judge, not Opus
**Phase:** 1 · **2026-09-05**

**Why:** Sonnet 5 ($2/$10 per MTok) is already well above the `claude-haiku-4-5` planner
($1/$5), which is the only property the judge needs. Opus 5 at $5/$25 is not worth 2.5× the cost
for this task.

---

### D-014 · Calibrate the judge against human labels
**Phase:** 1 · **2026-09-05**

Twenty itineraries generated on replayed tool data, hand-labelled by Manoj, with Cohen's kappa
between judge and human reported per rubric in the README.

**Why:** Planner and judge are both Claude models, and same-family judging carries documented
self-preference bias — one published case reached only 0.31 kappa against domain experts while
appearing to work. Using replayed tool data means the twenty itineraries cost Anthropic tokens but
**zero** SerpAPI searches. Validating the measurement instrument before trusting it is the point of
the exercise.

---

### D-015 · No Batch API
**Phase:** 1 · **2026-09-05**

Judge calls run synchronously.

**Why:** The 50% Batch discount applies to a handful of judge calls across five live trips. The
saving is cents; the cost is async job-polling code. Revisit if the live tier ever grows large.

---

### D-016 · Judge scores are not a standalone quality metric
**Phase:** 1 · **2026-09-07**

The calibration ran and the judge failed it. Against 20 hand-labelled itineraries,
quadratic-weighted kappa was 0.449 (moderate) for fairness, −0.071 (worse than chance) for
itinerary coherence, and undefined for trip-pitch quality. No phase may report a judge score as
evidence of quality without the accompanying kappa and bias figures from `evals/README.md`.

**Why:** D-014 predicted same-family self-preference and the data shows it directly: the judge
scored the planner's own prose 4 or 5 on every one of the 20 items the human scored 3, a +1.55
mean gap with zero exact agreement. Coherence agreement is no better than chance because the
judge will not reproduce the rater's harshest scores. Only fairness carries usable signal, and it
is bounded by the rater's own 5-of-9 intra-rater consistency. Recalibration is required after
rubric v2 and after the K-006 logistics repair, because both change what is being measured.

---

### D-017 · Rubric v1 is frozen; revisions become new versions
**Phase:** 1 · **2026-09-07**

The three rubrics that the committed labels were made against are immutable. `labels.json` pins
`rubric_version` (a hash of the rubric text) and `evals.calibrate` refuses to compare across a
change. A revised rubric ships as a new version alongside, with its own labelling pass.

**Why:** Editing a rubric in place would silently invalidate three hours of human labelling —
judging a new rubric against old labels measures rubric drift, not judge accuracy. The labelling
also showed v1 measures a narrower thing than the rater actually graded (coherence missed whether
the trip is interesting, fairness missed budget under-utilization, pitch missed presentation), so
a v2 is expected. See `docs/PRODUCT_FEEDBACK.md` F-29.
