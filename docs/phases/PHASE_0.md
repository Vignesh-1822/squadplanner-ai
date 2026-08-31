# Phase 0 — Close the Doors

**Branch:** `phase-0-security` · **Implementer:** Cursor · **Reviewer:** Codex
**Blocks:** every other phase. Nothing ships until this is green.

---

## Why this phase exists

Eight endpoints have no authentication, and they are live on the deployed demo. Worse than the
missing checks: **the server currently trusts the client's claim about identity.** `POST /trips`
accepts `created_by` in the request body, and `generate_trip` decides leadership by comparing
against that field — so a caller can create a trip in someone else's name and be its leader.

The governing principle for this phase: **identity is derived from the token, never accepted from
the request.**

---

## Objectives

### O1 · Identity comes from the token
- `POST /trips` requires auth. `created_by` is taken from the authenticated user and **removed from
  `CreateTripRequest`**.
- `GET /trips` — the `?email=` query parameter is **deleted, not secured**. The route returns only
  trips where the caller appears in `invited_members`. Add `limit`/`skip` pagination.
- No route anywhere accepts a caller-supplied identity.

### O2 · A three-tier authorization model
Implemented as reusable FastAPI dependencies in `api/middleware/authz.py`:

| Dependency | Rule |
|---|---|
| `require_member(trip_id)` | Caller's email appears in the trip's `invited_members` |
| `require_leader(trip_id)` | Caller's email equals the trip's `created_by` |
| `require_admin` | Caller's user document has `is_admin: true` |

Applied as:

| Route | Required |
|---|---|
| `POST /api/trips` | authenticated |
| `GET /api/trips` | authenticated (member-scoped results) |
| `GET /api/trips/{id}` | member |
| `GET /api/trips/{id}/result` | member |
| `GET /api/trips/{id}/stream` | member |
| `POST /api/trips/{id}/confirm-city` | **leader** |
| `POST /api/trips/{id}/refine` | **leader** (D-003) |
| `GET /api/trips/{id}/refinements/{rid}/stream` | member |
| `GET /api/admin/serpapi-usage` | **admin** |
| `POST /api/auth/logout` | authenticated (needs the user to bump `token_version`) |

Deliberately public, and asserted as such in the tests:
`POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/google`,
`GET /api/trips/by-invite/{code}`, `GET /health`, and FastAPI's `/docs`, `/redoc`, `/openapi.json`.

### O3 · Joining requires the invite code
`POST /trips/{id}/join` currently needs only a trip ID. Add a required `invite_code` in the body,
verified against the trip. Holding a trip ID must not be enough to join.

> **Contract change** — `joinTrip(id)` becomes `joinTrip(id, inviteCode)`. Record this in
> `docs/FRONTEND_CONTRACT.md` **only**. Do not touch `frontend/` — see D-007.

### O4 · Session lifecycle
- JWT expiry drops from 7 days to **24 hours** (D-005).
- Users gain a `token_version` integer (default `0`), issued as a JWT claim and compared in
  `get_current_user`. A mismatch is a 401. **This costs no extra database work** — that dependency
  already loads the user document.
- `POST /auth/logout` increments `token_version`, killing every outstanding token for that user.
- Users gain `is_admin: bool = False`.
- Both fields must be tolerated as absent on existing documents (treat as `0` / `False`).

### O5 · Transport and abuse limits
- Cookie `secure` flag driven by a new `COOKIE_SECURE` setting (default `False` locally, `True` in
  production).
- CORS origins driven by a new `CORS_ORIGINS` setting (comma-separated). The current hardcoded
  `localhost:5173/5174` does not include the deployed origin.
- `slowapi` rate limits: per-IP on `/auth/register`, `/auth/login`, `/auth/google`; per-user on
  `POST /trips`, `/generate`, `/refine`. In-memory storage is acceptable (single instance) —
  note the limitation in a comment.

### O6 · Data layer
- New `db/indexes.py` exposing a module-level `INDEX_SPECS` list and an `ensure_indexes()`
  coroutine, called from application startup.
  - `trips`: `trip_id` (unique), `invite_code` (unique), `created_by`, `invited_members.email`
  - `users`: `email` (unique)
  - `api_cache`: `key`, plus a **TTL index on `cached_at`**
  - `api_usage`: `type` + `month` (compound, unique)
- Move the ad-hoc `google_id_1` drop out of `main.py`'s startup handler into `ensure_indexes()`.
- **Move the SerpAPI quota counter** from `api_cache` to a new `api_usage` collection (D-006),
  including a one-time migration of the current month's `calls_used` so the guard does not reset.
- Remove the unused `StaticFiles` import in `main.py` (the `/debug` mount no longer exists).

### O7 · Proof
- `backend/tests/test_authz.py` (see success criteria below).
- `docs/THREAT_MODEL.md` mapping each control to the OWASP Top 10 for LLM Applications and the
  OWASP Top 10 for Agentic Applications.
- Repair the two pre-existing failures in `tests/test_preference_constraints.py` — they construct
  the removed pre-squad `CreateTripRequest` shape. Delete the three empty test files
  (`test_agent.py`, `test_scoring.py`, `test_tools.py`) or fill them; do not leave them empty.

### O8 · Restore the debug harness
`backend/debug_ui/index.html` is a complete 953-line manual test runner that is currently dead code —
the `/debug` mount was removed from `main.py`, leaving `StaticFiles` imported but unused. It is our
manual verification surface for every phase from here on (D-008).

- Re-mount it at `/debug` in `main.py`.
- Add a login step to the page so it works against the now-authenticated API. It should call the
  existing `/api/auth/login` and rely on the session cookie for everything after.
- Update it for the current API shape: the squad flow (`join` → `preferences` → `generate`), and
  `EventSource(url, { withCredentials: true })` for both SSE streams.
- **The static HTML itself stays public** and must be added to `PUBLIC_ROUTES` with a comment
  explaining why: the page contains no data, and serving it behind auth would make logging in from
  it impossible. Every API call it makes is authenticated normally.

---

## Out of scope — do not do these here

- **Prompt-injection defence and input sanitisation.** That is Phase 2. Phase 0 governs who gets in
  the door; Phase 2 governs what they may say once inside.
- **Any change under `frontend/` whatsoever.** That directory is byte-identical to upstream and
  must stay that way (D-007). Contract changes go in `docs/FRONTEND_CONTRACT.md`.
- Keeping the deployed `showcase/` demo working — it is expected to break (D-002).
- Refactoring `agent/`, the graph, or `itinerary.py`.
- Redis, external rate-limit storage, or refresh-token flows.

---

## Success criteria

All four commands must pass from `backend/`, with **no network and no MongoDB running**.

```bash
# 1 — the phase gate
./venv/bin/python -m pytest tests/test_authz.py -q

# 2 — nothing else regressed, and the pre-existing failures are gone
./venv/bin/python -m pytest tests/ -q --ignore=tests/test_integration.py

# 3 — wiring smoke check
./venv/bin/python -c "import main; print('ok')"

# 4 — index specification is declared correctly
./venv/bin/python -m pytest tests/test_indexes.py -q
```

### What `test_authz.py` must contain

1. **An anonymous route-table sweep.** Iterate `app.routes` — do not hand-list endpoints. For every
   route not in an explicit `PUBLIC_ROUTES` allow-list, call it with no cookie and assert the status
   is `401` or `403`, never `2xx`. Substitute any path parameter with a dummy value.
   *This is the important one: a route added in a later phase without auth fails this test
   automatically.*
2. **The public allow-list is asserted explicitly**, so making something public is a visible
   diff rather than an oversight.
3. **A role matrix**, using `app.dependency_overrides` to inject fake users and a fake trips
   collection — no live Mongo:
   - non-member → `GET /trips/{id}` returns 403
   - member → `GET /trips/{id}` returns 200
   - member (not leader) → `POST /trips/{id}/confirm-city` returns 403
   - member (not leader) → `POST /trips/{id}/refine` returns 403
   - leader → both return non-403
   - non-admin → `GET /admin/serpapi-usage` returns 403
4. **Identity cannot be spoofed**: `POST /trips` with a `created_by` in the body must not set
   ownership from that value.
5. **Token revocation**: a JWT carrying a stale `token_version` returns 401.

`test_indexes.py` asserts the contents of `INDEX_SPECS` — that each expected collection, key and
uniqueness/TTL option is declared. It must not require a database connection.

---

## Sub-phases

Implement in order; each should end at a committable state.

| # | Scope | Touches |
|---|---|---|
| **0.1** | Settings, session lifecycle, data layer. No route behaviour changes yet. | `config.py`, `services/auth_service.py`, `api/middleware/auth.py`, `api/routes/auth.py`, `db/indexes.py`, `main.py`, `tools/serpapi.py`, `api/admin.py`, `.env_example` |
| **0.2** | The authorization layer and its application to every route. | `api/middleware/authz.py` (new), `api/trips.py`, `api/hitl.py`, `api/refinements.py`, `api/squad.py`, `api/admin.py` |
| **0.3** | Rate limiting. | `main.py`, `api/routes/auth.py`, `api/trips.py`, `api/squad.py`, `api/refinements.py`, `requirements.txt` |
| **0.4** | Restore and re-auth the debug harness (O8). | `main.py`, `backend/debug_ui/index.html` |
| **0.5** | Proof and documentation. | `tests/test_authz.py`, `tests/test_indexes.py`, `tests/test_preference_constraints.py`, `docs/THREAT_MODEL.md`, `docs/FRONTEND_CONTRACT.md` |

---

## Known traps

- **The SerpAPI counter shares `api_cache` with cached responses.** A TTL index on `cached_at`
  spares it only because that document has no such field. Migrate it to `api_usage` (O6) rather
  than relying on that. Verify `calls_used` for the current month survives the migration.
- **SSE authenticates by cookie.** `EventSource` cannot send headers. The browser must use
  `new EventSource(url, { withCredentials: true })`, and CORS must name the origin explicitly —
  `allow_origins=["*"]` is invalid alongside `allow_credentials=True`. Get this wrong and every
  stream 401s with no obvious cause. The client half is Vignesh's; record it in the contract doc.
- **`api/trips.py` and `api/squad.py` share the `/trips` prefix.** Route ordering matters:
  `/trips/by-invite/{code}` must not be shadowed by `/trips/{trip_id}`.
- **Existing user documents have neither `token_version` nor `is_admin`.** Absent must mean
  `0` and `False`, or every current session breaks and nobody can log in.
- **`backend/api/trips.py` is Vignesh's most-edited file** (six commits). This phase changes it
  heavily. Keep the diff tight and merge upstream as soon as the phase is green.
- **`backend/api/middleware/auth.py`, `api/routes/auth.py` and `services/auth_service.py` are also
  his.** Change behaviour, not structure — don't reorganise his auth module while you're in it.

---

## Coordination

This branch merges into `Vignesh-1822/squadplanner-ai` via PR as soon as it is green (D-009).
Before opening it, tell Vignesh two things:

1. **Every trip route now requires authentication**, and `POST /trips` no longer accepts
   `created_by` — it comes from the session. `docs/FRONTEND_CONTRACT.md` has the full matrix.
2. **`EventSource` must now pass `{ withCredentials: true }`**, or both SSE streams will 401.

`frontend/` is untouched by this PR, so there is nothing for him to merge or resolve there.
