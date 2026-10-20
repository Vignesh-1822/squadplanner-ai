# Backend briefing for the frontend side

**For Vignesh, and for any agent working on `frontend/`.** This explains what has been happening
on the backend, what it means for the UI, and how the work is organised so the two halves stay in
step. Everything here is current as of 2026-09-07 and **subject to change** — the roadmap is being
revised right now.

This is the *why* and the *direction*. For the actual API surface — every endpoint, request shape,
response shape and status code — [`FRONTEND_CONTRACT.md`](FRONTEND_CONTRACT.md) is the source of
truth and stays authoritative where the two disagree.

---

## The short version

Two phases shipped. **Phase 0** locked down the API: everything is authenticated now, and the
server no longer believes anything a client says about who it is. **Phase 1** built a measurement
layer — evals, tracing, per-node cost accounting — and **changed no product behaviour at all**, on
purpose, so we have an honest baseline to improve from.

Phase 1 also turned up a set of real defects in the generated itineraries. **Some of what the UI
renders today is visibly wrong, and it is not the frontend's fault.** The list is below so you
don't design around it.

---

## Phase 0 — the API is closed now

Eight endpoints previously had no authentication, and `POST /trips` accepted `created_by` in the
request body, meaning any caller could create a trip owned by anyone. Both are fixed.

What this changes for the client:

- **Every private request needs the session cookie.** `apiFetch` must send
  `credentials: "include"`, and both SSE clients need `new EventSource(url, { withCredentials: true })`.
- **Never send identity.** `created_by` in a request body is ignored; the server reads it from the
  cookie. Same for any member email you might be tempted to pass.
- **Expect 401 and 403 as normal states**, not just error cases. 401 means "not signed in", 403
  means "signed in but not a member / not the leader". The authorization matrix in the contract doc
  says which routes are member-only versus leader-only.
- **Rate limits are live**, so `429` is now possible:

  | Route | Limit |
  |---|---|
  | `POST /auth/register` | 5 / minute |
  | `POST /auth/login`, `POST /auth/google` | 10 / minute |
  | `POST /trips` | 10 / hour |
  | `POST /trips/{id}/generate` | 3 / hour |
  | `POST /trips/{id}/refine` | 10 / hour |

- **The public invite preview returns no email addresses.** `GET /trips/by-invite/{code}` gives
  trip name, invite code, member count and the leader's display name — nothing else. It is the one
  route that stays public, so it cannot leak the squad.
- Logging out revokes existing tokens, so a signed-out session cannot be resurrected from a stale
  cookie.

---

## Phase 1 — measurement, and nothing else

Phase 1 deliberately changed no behaviour. It added:

- **An offline replay layer.** The whole agent graph can run with recorded API responses and
  recorded model responses, so a full 30-case evaluation runs in about 20 seconds, with no network,
  no database, no API keys, and no cost. That is what makes it possible to change the backend and
  know within seconds whether anything broke.
- **Tracing** via LangSmith, with member email addresses stripped before anything leaves the
  process.
- **Cost and latency per node**, persisted on the trip and exposed at
  `GET /api/trips/{trip_id}/telemetry` (member-only). Roughly $0.04 of model spend per trip. If you
  ever want to show "this plan cost X to generate", the data is there.
- **Automated scoring** — budget compliance, dietary coverage, hard avoids, date correctness,
  geographic sanity — plus a second model acting as a quality judge.

One result worth knowing: **the judge failed its calibration.** We hand-scored 20 itineraries and
compared. Agreement was moderate on fairness, no better than chance on coherence, and on
trip-pitch quality the judge rated the planner's own prose 4 or 5 on every single item a human
scored 3. So we do not currently trust automated quality scores, and no phase may quote one
without the calibration figures beside it. Details in `backend/evals/README.md`.

---

## What is currently broken in the output

These are backend defects, tracked in [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md). They will be fixed in
an upcoming phase. **Please don't build UI workarounds for them, and don't treat the current
output as the target.**

| ID | What you'll see | Why |
|---|---|---|
| **K-006** | The hotel is sometimes in the wrong state entirely — a Texas trip booking a South Carolina hotel — so every day starts with a 2,000 km travel leg. 10 of 20 sample itineraries book a hotel in a different state from the destination; 14 of 20 contain a travel leg over 100 km. | Hotel search sends a bare city name with no state, so an ambiguous name resolves to the wrong city. |
| **K-007** | Days look sparse: often only two activities, sometimes nothing between lunch and dinner. | A repair loop detects the impossible travel time from K-006 and responds by *deleting activities*. It hits its retry limit on every single trip and gives up. |
| **K-002** | Every flight shows the same $300 estimate for every member. | Flight search sends a city name where an airport code is required, so it always falls back to a placeholder. |
| **K-008** | Lodging cost looks far too low for large groups. | One room's price is divided across the whole squad. No room-count maths exists. |
| **K-010** | Breakfast appears in the meal list but is often missing from the timed schedule, so the rendered day starts at lunch. | The validator counts meal strings but never checks the schedule contains them. |
| **K-004** | **Frontend-visible.** If a trip hits severe budget pressure, the graph asks for a second city choice — but the SSE helper only handles one pause. The stream can end while the graph is still waiting. | Production streaming resumes once and returns. The eval runner loops correctly, so this is a streaming bug, not a planner bug. |

K-004 is the one most likely to bite the UI. If a stream goes quiet with the trip still in a
planning state, that's this, not your client.

---

## How the work is organised

The backend runs on a phase-by-phase loop, documented in [`PROCESS.md`](PROCESS.md):

1. A phase gets a written spec in `docs/phases/PHASE_N.md` before any code.
2. Work happens against that spec. Divergence gets raised, not silently absorbed.
3. Every phase ends with executable success criteria — commands that either pass or don't.
4. Decisions that would otherwise get re-argued go in [`DECISIONS.md`](DECISIONS.md) with a reason.
   D-001 upward. If something in the backend looks like an odd choice, it's probably explained there.
5. Defects found but deliberately not fixed go in [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) rather than
   being quietly patched mid-phase.

The roadmap is in [`ROADMAP.md`](ROADMAP.md). It's about to be rewritten: hand-scoring those 20
itineraries produced a list of product problems in
[`PRODUCT_FEEDBACK.md`](PRODUCT_FEEDBACK.md), and nineteen of the twenty-nine findings have no home
in the current plan. Expect the phase list after Phase 1 to change shape.

### Working alongside each other

- **`frontend/` is yours.** Nothing on the backend side touches it, including
  `frontend/src/services/`. When the API changes, [`FRONTEND_CONTRACT.md`](FRONTEND_CONTRACT.md)
  gets edited — never your JavaScript.
- **`backend/` is the other direction.** If you need something from the API that doesn't exist,
  the fastest path is to say so rather than to work around it.
- **`backend/api/trips.py` is the contested file.** Both sides have edited it repeatedly, and our
  last merge produced a function that couldn't run because each side had independently changed how
  a helper was called — neither change was wrong alone. Merging upstream promptly is the cheapest
  way to avoid a repeat.
- **`backend/debug_ui/` is a test harness, not a product surface.** It exists so backend work can
  be exercised without depending on the real UI. Nothing there is a design proposal.

### If you're running the backend locally

```bash
cd backend
./venv/bin/python -m uvicorn main:app --reload      # dev server on :8000
./venv/bin/python -m pytest tests/ -q               # deterministic, no network or DB
```

Two things worth knowing: **don't run `tests/test_integration.py`** — it spends real API quota, and
SerpAPI is capped at 200 searches a month, which is the binding cost constraint on this project.
And `backend/.env` is not in the repo; `backend/.env_example` lists what's needed.

---

## What's next

The next phase is being planned now. In rough priority: fix the logistics defects above (K-006 and
K-007 first, since they make the output unusable), then the cost-realism problems, then a decision
about how much the planner should ask the user versus decide on its own.

If any of that changes what the API returns, it lands in
[`FRONTEND_CONTRACT.md`](FRONTEND_CONTRACT.md) before it lands in code, and this document will be
updated alongside.
