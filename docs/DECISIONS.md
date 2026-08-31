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
