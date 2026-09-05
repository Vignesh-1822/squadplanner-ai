# Frontend Tasks — SquadPlanner AI

Working backlog for `frontend/`. Scope is `frontend/` only; `showcase/` is a temporary demo and
out of scope.

**The situation as of 2026-09-04:** the backend now implements the full async squad flow —
join, per-member preferences, leader-gated generation, streaming, HITL, result, refinement.
`frontend/` calls **none of it**. Every remaining task here is frontend wiring against endpoints
that already exist and work.

Authoritative API reference: [`docs/FRONTEND_CONTRACT.md`](../docs/FRONTEND_CONTRACT.md).
When this doc and the contract disagree, the contract wins.

**Status:** `TODO` · `IN PROGRESS` · `DONE` · `BLOCKED` · `DROPPED`
**Last updated:** 2026-09-04

---

## Execution Order

| Phase | Goal | Tasks | Status |
|---|---|---|---|
| **1** | Correct the preference payload shape | F5, F6, F8, F7 | **DONE** |
| **2** | Wire preferences to the backend | F1 | **DONE** |
| **3** | Lobby: readiness + leader-gated generation | F19, F2, F15 | **DONE** |
| **4** | Planning, HITL and itinerary screens | F20 ✓, F21, F3 | **F20 DONE** |
| **5** | Guest invite flow | F4 | TODO |
| **6** | Architecture debt (carried along, not deferred) | F9, F10, F11, F12 | TODO |
| **7** | Placeholders and papercuts | F13–F18 | TODO |

Phases 2→5 follow the user's path through the app, so each one is demoable on its own.
Phase 6 items are picked up inside whichever phase touches those files.

---

## Backend status — what already exists

Committed in `d553490` / `6a713ae`. All under `/api`, all in `backend/api/squad.py` unless noted.

| Endpoint | Notes |
|---|---|
| `GET /trips/by-invite/{code}` | **Public.** What a guest sees before logging in. |
| `POST /trips/{id}/join` | Auth. Flips caller `pending` → `joined`. |
| `POST /trips/{id}/preferences` | Auth. Upserts, marks member `ready`. **409** once planning started. |
| `POST /trips/{id}/generate` | **Leader only (403).** Assembles `initial_state.members`, unlocks the stream. |
| `GET /trips/{id}` | Lobby poll. Returns `status`, `ready_count`, `total_count`, `all_ready`, `can_generate`. |
| `GET /trips/{id}/result` | Completed itinerary, server-side. **409** if not finished. |
| `GET /trips/{id}/stream` | SSE. Also `/refinements/{rid}/stream`. |

**Where preferences are stored:** nested per member inside `trips.invited_members[]` as a
`preferences` object — *not* in `initial_state.members`. `initial_state.members` stays empty until
`POST /generate` assembles it from every member who has submitted. One array, no second structure
to keep in sync.

---

## Decisions

### D1 · `created_by` — *superseded by Phase 0*
Recorded here as storing the user `_id`. The backend instead keeps the email and is removing
client-supplied `created_by` entirely — the server will take it from the session. The stability
concern stands but is now the backend's call; nothing for the frontend to do beyond dropping the
field from `createTrip` when Phase 0 lands (see F21).

### D2 · The server decides who the leader is — **satisfied, differently**
Rather than a `viewer_is_leader` field, `GET /trips/{id}` returns `is_leader` per member plus
`can_generate`, and `POST /generate` enforces leader-only with a 403. The frontend must never gate
on its own identity math — drive the button off `can_generate` and let the 403 be the real
boundary.

### D3 · `is_leader` derived server-side — **done**
`squad.py::generate_trip` normalizes to exactly one leader (first wins) before building
`initial_state.members`, satisfying `input_parser.py:57`.

### D4 · **Strict gate — every invited member must submit** — decided 2026-09-04
The backend ships a loose gate (`can_generate` = leader ready only). Vignesh chose strict.
Implemented in three parts, not one:

1. **`trips.py:257`** — `can_generate = all_ready and trip.get("status") in (None, "pending",
   "collecting")`. `all_ready` (line 254) already implies the leader is ready, so `leader_ready`
   drops out. Changing the meaning here keeps the policy in one place; the UI keeps reading
   `can_generate` and stays ignorant of the rule.
2. **`squad.py`, after line 262** — enforce it server-side, or the gate is decoration:
   `not_ready = [m["email"] for m in invited_members if not m.get("preferences")]` → **422**
   `"Waiting on preferences from: ..."`. Per the contract that `detail` is surfaced verbatim.
3. **`DELETE /trips/{id}/members/{email}`** (leader-only, `collecting` or earlier, cannot remove
   the leader) — the escape hatch. Without it one person who ignores their invite blocks the trip
   permanently, since `total_count` includes invitees who never signed up. Counting only *joined*
   members instead has the same hole one step later.

Frontend renders the button only when `me.is_leader`, enables on `can_generate`, and **must show
why it is disabled** — "Waiting on 2 of 4 — friend@x.com". A greyed button with no reason is worse
than no button.

### D5 · Member status vocabulary is `pending → joined → ready`
`accepted` is never emitted by the backend. See F19.

---

## Phase 2 — Wire preferences

### F19 · The UI checks for a status the backend never sends — `DONE`
`TripLobby.jsx:67` and `MyTrips.jsx` test `member.status === "accepted"`. The backend emits only
`pending`, `joined`, `ready` (D5), so **every member renders as "Invitation Sent" forever** and the
readiness count is permanently 0. Cheap fix, but it invalidates the lobby until done.

**Done when:** member status rendering uses `pending` / `joined` / `ready`.

**Done.** New `src/lib/tripStatus.js` holds the vocabulary for both trip and member status so it
cannot drift again. `MyTrips` was checking trip statuses (`"ready"`, `"synced"`) the backend never
emits either — now mapped onto `complete` / `generating`+`city_selection` / everything else.

### F1 · Preferences are collected and thrown away — `DONE`
`TripPreferences.jsx:58` builds the correct payload via `buildMemberPayload()` and only
`console.debug`s it.

Backend is ready — `POST /trips/{id}/preferences`. Remaining work is all frontend:

- **`ApiList.js` is missing the clients.** The contract claims every endpoint already has a JS
  client there; it does not — only `getMe/register/login/googleAuth/logout` and
  `getTrips/getTripById/createTrip` exist. Add `submitPreferences`, `generateTrip`, `joinTrip`,
  `getTripByInvite`, `getTripResult`, `confirmCity`, `refineTrip`, `streamUrl`.
- Rename `availability` → `date_windows` in the request body to match the contract.
- Drop `member_id` / `name` / `is_leader` from `buildMemberPayload` — the server derives all three
  from the session. Phase 1 targeted the graph's shape; the API's shape is narrower.
- Replace `console.debug` with a React Query `useMutation` (starts F10); disable the button while
  in flight, toast the error `detail` verbatim.
- Prefill from `has_preferences` so editing works — the endpoint upserts.
- Surface the **409** ("Trip has already started planning") as a real message.

**Done when:** submitting marks the member `ready` and the lobby reflects it.

**Done.** `ApiList.js` now carries the full API surface (10 new clients + `BASE_URL` exported from
`services/index.js` so `streamUrl` can build SSE endpoints). `buildMemberPayload` became
`buildPreferencesPayload` — identity fields dropped, `availability` renamed `date_windows`.
`TripPreferences` submits via a React Query `useMutation`, disables while in flight, surfaces the
backend `detail` verbatim, and routes to the lobby on success.

**Deferred: prefill.** Editing your own preferences needs the stored values back, and no endpoint
returns them — `GET /trips/{id}` exposes only the `has_preferences` boolean. It also cannot know
who is asking, because that route is still unauthenticated. So prefill is blocked on Phase 0
adding auth there; the endpoint already upserts, so re-submitting works today.

---

## Phase 3 — Lobby

### F20 · `EventSource` needs `withCredentials` — `DONE`
`EventSource` cannot send an `Authorization` header, so the cookie is the only mechanism — and
cookies are withheld cross-origin (5173 vs 8000) without `withCredentials`.

**Done.** `src/hooks/useEventStream.js` wraps it so F3 cannot get it wrong. It also handles the
second EventSource trap: the browser reconnects automatically whenever a stream ends, *including*
the clean end after a run completes — left alone it reopens and replays the run. Terminal events
close it explicitly via `closeOn`.

### F2 · The lobby is a terminal dead end — `DONE`
No "Scout Destinations" action; nothing ever calls `POST /generate`.

- Button visible only to the leader, enabled on `can_generate` (strict per D4), with the
  blocking members named beside it.
- Leader-only remove (✕) on pending members — the D4 escape hatch.
- Poll `GET /trips/{id}`; on `status` → `generating` / `city_selection`, route everyone to planning;
  on `complete`, to the itinerary.
- Real readiness bar from `ready_count / total_count` — closes **F15**.
- Surface generate's **422** messages verbatim: nobody ready, >8 members, leader hasn't submitted,
  no overlapping availability. They are written for users.

**Done when:** the leader can start planning and non-leaders cannot see the button.

**Done.** `TripLobby` rewritten on React Query. Leader found via `invited_members` + the session
email; Scout Destinations renders for the leader only, enabled on `can_generate`, and when disabled
names who is missing. Non-leaders see the same count without the button. Remove ✕ wired to
`removeMember`. Readiness bar driven by `ready_count / total_count` (**F15 closed**). Polling is now
30s while collecting, 5s once `all_ready`, and stopped at terminal states — plus refetch-on-focus
and automatic pause while the tab is hidden.

**Interim:** pressing the button starts a real run, but F3's screens don't exist yet, so the lobby
detects `generating` / `complete` and reports it in place rather than routing to a blank page.
Marked `TODO(F3)`.

---

## Phase 4 — Planning, HITL, itinerary

### F21 · Phase 0 breaking changes — `TODO`
Backend security work in flight. When it lands: `POST /trips` stops accepting `created_by`
(remove it from `NewTrip.jsx`), `GET /trips` loses `?email=` and returns only your own trips
(update `getTrips` and `MyTrips.jsx`), and `joinTrip(id)` becomes `joinTrip(id, inviteCode)`.

### F3 · Three screens don't exist — `TODO`
No streaming page, no HITL city-selection, no itinerary view.

- `/trips/:tripId/planning` — SSE progress; on `HITL_REQUIRED` render the 5 candidate cards and
  POST `/confirm-city`; on `TRIP_COMPLETE` go to the itinerary.
- `/trips/:tripId/itinerary` — load `GET /result` (409 = not finished), render days/hotel/flights,
  plus the refinement box.
- `TripPreferences.jsx:57` also falls back to `navigate("/dashboard")`, a route that doesn't exist
  → blank screen.

A rough but correct reference implementation of all three (plus a Leaflet `ItineraryMap`) exists on
branch `wip/solo-frontend-attempt` — deliberately kept off `main` so the design is ours, but useful
for the SSE handling: `git show wip/solo-frontend-attempt:frontend/src/pages/Planning.jsx`.

**Done when:** a trip runs end to end: submit → generate → stream → pick a city → itinerary.

---

## Phase 5 — Guest invite flow

### F4 · `/join/:code` doesn't exist — `TODO`
`TripLobby.jsx:43` and `:179` copy `${origin}/join/${invite_code}`. No route, no page — every
invitee lands on a blank screen.

Backend is ready (`GET /trips/by-invite/{code}` public, `POST /trips/{id}/join` auth'd). Needed:
the route, and a post-auth redirect in `Auth.jsx` — unauthenticated guests stash the code in
`sessionStorage.pendingInvite`, sign in, and resume.

**Done when:** an invitee opens the emailed link, signs in, and lands in the lobby as `joined`.

---

## Phase 6 — Architecture debt

### F9 · `sessionStorage` carries trip identity — `TODO` · *mostly done*
Preferences and the lobby now read `:tripId` from the route; the bare `/trips/lobby` route is gone
since every caller passes an id. Only `NewTrip` → `InvitesSent` still hands off via sessionStorage.
`NewTrip.jsx:35`, `InvitesSent.jsx:13`, `TripPreferences.jsx:53`, `TripLobby.jsx:17`. Dies in a new
tab and makes URLs unshareable — fatal for an invite-based app. `/trips/:tripId/lobby` already
exists; `/trips/preferences` needs a `:tripId` too. Note `pendingInvite` (F4) is a legitimate use.

### F10 · React Query installed, provided, never used — `TODO` · *mostly done*
`TripPreferences` (mutation) and `TripLobby` (query + two mutations) are converted, including the
state-keyed `refetchInterval`. `MyTrips`, `InvitesSent` and `authStore` still hand-roll
`useEffect` + loading flags.

### F11 · Two competing user stores — `TODO`
`UserProvider` is mounted in `main.jsx` and never consumed; `authStore` is real. Delete it, plus
empty `store/index.js` and `components/templates/index.js`.

### F12 · `RootLayout` and `SideMenu` are orphaned — `TODO`
No route mounts them. `SideMenu` hardcodes `"Vignesh"` / `"@vignesh"`. Adopt or delete.

---

## Phase 7 — Placeholders and papercuts

### F13 · `Home.jsx` is 100% fake — `TODO`
Hardcoded "Vignesh", "140 Miles Traveled", "PARIS, FRANCE", "$864", and a `EuropeMap` for a
**US-only** dataset. It is the post-login landing page.

### F14 · Five dead nav links — `TODO`
`HomeHeader`: Explore / Shared Trips / Stats. `SideMenu`: Help. Plus `/settings`. No 404 route,
no error boundary.

### F15 · Hardcoded readiness — `DONE` · *closed by F2*
`TripLobby.jsx:68` sets `readiness = 60` while the real counts sit unused two lines above.

### F16 · Registration errors always show the wrong message — `TODO`
`Auth.jsx:33` checks `err.message?.includes("409")`, but `apiFetch` throws `body.detail` and never
the status code — duplicate signups read "Invalid email or password."

### F17 · Two design systems for one component — `TODO`
antd + a full `ConfigProvider` override for a single `RangePicker`, while unused shadcn
`date-picker` / `calendar` sit in `components/ui/`. `dayjs` is imported but not in `package.json` —
it resolves only transitively through antd. (Note: the contract requires a *range* picker, so
antd may be worth keeping — decide rather than drift.)

### F18 · Minor — `TODO`
`alert()` at `NewTrip.jsx:41` while `sonner` is used everywhere else. Hardcoded
`googleusercontent.com` avatar and inline `dangerouslySetInnerHTML` CSS in `Auth.jsx`.

---

## Watch list

- **Single-day overlap.** `_compute_group_window` can return `start == end`; `input_parser` then
  computes duration `0` and raises "duration must be 2–14 days". Surfaces as a confusing error.
  Backend issue, but the UI is where it will be seen.
- **`POST /join` is permissive** — any authenticated user with the link joins; no check against
  `invited_emails`.
- Planner hard caps: **8 members**, **5 days**.

---

## Changelog

- **2026-09-05** — **F20 done.** `useEventStream` hook: `withCredentials` for cookie auth, plus
  `closeOn` so a finished run doesn't get replayed by EventSource's automatic reconnect.
- **2026-09-04** — **Lobby fixes from testing.** The creator was missing from the squad on trips
  created before the creator-as-member change, which also undercounted `total_count` and would have
  blocked generation (the planner needs exactly one leader) — `GET /trips/{id}` now heals that on
  read and persists it, alongside the existing `invited_emails` backfill. Added a `Leader` badge and
  a `(You)` marker on member rows, and a "Your turn" card linking to the preferences form when you
  have not submitted. The waiting-on list says "you" instead of repeating your own name.
  *Note: "1 of undefined" was a stale backend process — the count fields arrived with the squad
  commit, so uvicorn needs a restart after pulling.*
- **2026-09-04** — **Phase 3 done (F19, F2, F15).** Added `src/lib/tripStatus.js` as the single home
  for the status vocabulary. `TripLobby` rewritten on React Query with the leader-gated Scout
  Destinations button, a named waiting-on list, remove-member ✕, a real readiness bar, and polling
  keyed to state (30s → 5s when all ready → stopped at terminal). `MyTrips` remapped onto real trip
  statuses. Removed the bare `/trips/lobby` route. Frontend lint errors 15 → 6, all remaining ones
  pre-existing in untouched files; build clean.
- **2026-09-04** — **F1 done, plus the backend it needed.** Backend: strict `can_generate`
  (`all_ready` + status), 422 enforcement on `POST /generate` naming who is missing,
  new leader-only `DELETE /trips/{id}/members/{email}`, and member enrichment batched into one
  user query instead of one per member. Rewrote `tests/test_trips_api.py` — it had been failing
  since the squad refactor against the old response shape — now 9 tests covering the gate, the
  single-query guarantee, and remove-member permissions. Frontend: full `ApiList`,
  `buildPreferencesPayload`, `TripPreferences` wired via `useMutation`, preferences route now
  carries `:tripId`. Backend 41 passed / 2 pre-existing failures (both showcase-era). Frontend
  lint and build clean.
- **2026-09-04** — **D4 decided: strict gate.** Every invited member must submit before the leader
  can generate. Needs a backend change in two places plus a new remove-member endpoint — recorded
  under D4; not frontend-only.
- **2026-09-04** — Doc reconciled against the backend's committed squad flow (`d553490`, `6a713ae`).
  F1/F2/F4/F7 backend halves are done; every remaining task is frontend wiring. Added F19 (status
  vocabulary bug), F20 (`EventSource` credentials), F21 (Phase 0 breaking changes), D5, and a watch
  list. Re-ordered into user-journey phases.
- **2026-09-04** — Recorded D1–D4 and folded the leader-only Scout Destinations gate into F2.
- **2026-09-04** — **Phase 1 complete (F5, F6, F8, F7).** Added `src/lib/tripPayload.js` with a pure
  `buildMemberPayload()`; fixed the preference keys and 0–100 → 0.0–1.0 scale; added dietary
  toggle chips; folded the orphaned "Carry-on Only" toggle into `preference_notes`. Lint clean,
  build passes.
- **2026-09-04** — Backlog created from a full frontend review.
