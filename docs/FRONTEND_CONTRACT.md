# Frontend ↔ Backend Contract

> **Phase 0 security contract.** Every private request uses the httpOnly session cookie.
> `apiFetch` must send `credentials: "include"`, and both SSE clients must use
> `new EventSource(url, { withCredentials: true })`. The backend derives identity from that cookie;
> clients never submit their own identity.

**For Vignesh.** The backend implements a full async "squad" flow. `frontend/` currently
implements only part of it. This document is the complete contract so the UI can be built
without reading the Python.

All routes are mounted under `/api` (see `backend/main.py`). Base URL comes from
`VITE_API_BASE_URL`, defaulting to `http://localhost:8000/api`.

The JS client for every endpoint below already exists in
[`frontend/src/services/ApiList.js`](../frontend/src/services/ApiList.js) — import from there,
don't re-declare fetches.

## Authorization matrix

| Route | Access |
|---|---|
| `POST /auth/register`, `POST /auth/login`, `POST /auth/google` | Public |
| `POST /auth/logout`, `GET /auth/me` | Authenticated |
| `POST /trips`, `GET /trips` | Authenticated |
| `GET /trips/by-invite/{code}` | Public |
| `POST /trips/{id}/join` | Authenticated with matching invite code |
| `POST /trips/{id}/preferences` | Member |
| `GET /trips/{id}`, `/result`, `/stream` | Member |
| `POST /trips/{id}/generate`, `/confirm-city`, `/refine` | Leader |
| `GET /trips/{id}/refinements/{rid}/stream` | Member |
| `GET /admin/serpapi-usage` | Admin |

`POST /auth/logout` increments the user's session version and revokes every outstanding token for
that account. Tokens otherwise expire after 24 hours.

## The flow

```
Leader                                    Guest
──────                                    ─────
POST /trips                    ──────►    (email invite w/ invite_code)
  ↓                                          ↓
POST /trips/{id}/preferences              GET  /trips/by-invite/{code}   (public)
  ↓                                          ↓  login if needed
  │                                       POST /trips/{id}/join
  │                                          ↓
  │                                       POST /trips/{id}/preferences
  ↓  (poll GET /trips/{id} until can_generate)
POST /trips/{id}/generate
  ↓
GET  /trips/{id}/stream          (SSE — node progress)
  ↓  event: HITL_REQUIRED
POST /trips/{id}/confirm-city
  ↓  event: TRIP_COMPLETE
GET  /trips/{id}/result
  ↓  optional
POST /trips/{id}/refine  →  GET /trips/{id}/refinements/{rid}/stream  (SSE)
```

## Endpoints

### `POST /trips` — authenticated
```json
{ "trip_name": "Chicago Weekend", "invited_emails": ["guest@example.com"] }
```
Do not send `created_by`; ownership always comes from the session. The returned `stream_url` is
relative to the `/api` base.

### `GET /trips?skip=0&limit=50` — authenticated
Returns only trips where the caller is a member. The `email` query parameter no longer exists.
`skip` must be non-negative; `limit` is 1–100.

### `GET /trips/by-invite/{invite_code}` — public, no auth
What a guest sees before logging in. This intentionally excludes member email addresses.
```json
{ "trip_id": "...", "trip_name": "...", "invite_code": "...",
  "member_count": 4, "leader_name": "Alice" }
```

### `POST /trips/{trip_id}/join` — auth required
```json
{ "invite_code": "the-code-from-the-invite-link" }
```
Flips the caller from `pending` → `joined`. A trip ID without the matching code is rejected.

### `POST /trips/{trip_id}/preferences` — auth required
Each member submits their own. Marks them `ready`. Rejected with **409** once the trip has
started planning.
```json
{ "origin_city": "ORD", "budget_usd": 1500, "food_restrictions": ["vegan"],
  "preference_vector": { "nightlife": 50, "food": 80, "outdoor": 60,
                         "urban": 40, "shopping": 20 },
  "preference_notes": "No clubs, relaxed mornings.",
  "date_windows": [{ "start_date": "2026-07-10", "end_date": "2026-07-20" }] }
```
**Slider keys.** The backend canonicalizes to exactly five dimensions:
`outdoor, food, nightlife, urban, shopping`. It accepts 0–100 or 0–1 and divides by 100 when
`> 1`. `nature` and `adventure` are both aliased onto `outdoor` and **averaged** — so shipping
separate Nature and Adventure sliders silently halves their weight against a single Outdoor
slider. Ship five sliders matching the canonical names.
Source: `backend/api/squad.py::canonicalize_vector`.

**Date windows** are per-member availability *ranges*, not the trip dates. The backend
intersects every member's windows and picks the earliest contiguous run, capped at 5 days.
Zero overlap → **422**. This needs a range picker, not a single date pair.

### `GET /trips/{trip_id}` — the lobby poll
```json
{ "trip_id": "...", "trip_name": "...", "invite_code": "...",
  "status": "pending | collecting | generating | city_selection | complete",
  "created_at": "...", "expires_at": "...",
  "invited_members": [{ "email": "...", "status": "...", "name": "...",
                        "avatar_url": "...", "is_leader": true,
                        "has_preferences": true }],
  "ready_count": 2, "total_count": 4, "all_ready": false, "can_generate": true }
```
Member `status` values: `pending` → `joined` → `ready`. **The old UI checked for
`"accepted"`, which the backend never emits** — that's why the lobby readiness bar was stuck.
Drive the "Generate" button off `can_generate`, and the progress bar off
`ready_count / total_count`. When `status` becomes `generating` or `city_selection`, route
everyone to the planning screen; on `complete`, to the itinerary.

### `POST /trips/{trip_id}/generate` — **leader only** (403 otherwise)
Body optional: `{ "start_date": "...", "end_date": "...", "group_notes": "..." }` to override
the computed window. Returns `{ status: "generating", member_count, start_date, end_date,
stream_url }`. Errors: **422** if nobody is ready, >8 members, the leader hasn't submitted
preferences, or no overlapping availability. Surface `detail` verbatim — the messages are
written for users.

### `GET /trips/{trip_id}/stream` — member-only SSE
Emits node-progress events, then one of:
- `HITL_REQUIRED` — payload carries `candidate_destinations` (5 cards). Render them and wait.
- `TRIP_COMPLETE` — planning finished; fetch `/result`.
- error events.

`EventSource` cannot send an `Authorization` header. Construct both trip and refinement streams
with `{ withCredentials: true }`, or the stream returns 401.

### `POST /trips/{trip_id}/confirm-city` — leader only
`{ "selected_destination": "...", "selected_destination_coords": { "lat": 0, "lng": 0 } }`
Resumes the paused graph. The same SSE stream continues.

### `GET /trips/{trip_id}/result`
The completed itinerary, server-side — so a page refresh or a new device still works.
**409** if the trip hasn't completed.
```json
{ "trip_id": "...", "trip_pitch": "...", "itinerary": { "days": [...] },
  "preference_constraints": {}, "constraint_satisfaction": {},
  "decision_log": [], "refinement_history": [] }
```

### `POST /trips/{trip_id}/refine` (leader) → refinement stream (member)
Natural-language edits ("Make Day 2 cheaper"). Second call is SSE and streams the updated
itinerary, which replaces the current one in place.

## Routes the UI needs

Not yet in `frontend/src/routes/index.jsx`:

| Route | Purpose |
|---|---|
| `/join/:code` | Guest invite landing. Unauthed → stash `code` in `sessionStorage.pendingInvite`, send to `/auth`, resume after login. |
| `/trips/:tripId/planning` | Live SSE progress + the HITL destination-choice cards. |
| `/trips/:tripId/itinerary` | Completed itinerary + map + refinement box. |

`frontend/src/pages/Auth.jsx` needs the post-auth redirect that consumes `pendingInvite`.

## Reference implementation

A working (rough) version of all three pages, an `ItineraryMap` (Leaflet), and the
`format`/`map`/`tripStorage` helpers exists on the **`wip/solo-frontend-attempt`** branch.
It was deliberately left off `main` so the UI is yours to design, but it is a correct
reference for the SSE handling and payload shapes:

```bash
git show wip/solo-frontend-attempt:frontend/src/pages/Planning.jsx
```

## Known gaps

- Anyone with the valid invite code may join. There is no allow-list check against
  `invited_emails`.
- The planner hard-caps at **8 members** and **5 days**.
- `can_generate` only requires the *leader* to be ready, not everyone. `all_ready` is reported
  separately if you want a stricter gate in the UI.
