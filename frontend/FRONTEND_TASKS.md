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
| **4** | Planning, HITL and itinerary screens | F20 ✓, F3a ✓, F3b ✓, F21 | **DONE** (F21 pending Phase 0) |
| **5** | Guest invite flow | F4 | **DONE** |
| **6** | Architecture debt (carried along, not deferred) | F9, F10, F11, F12 | **DONE** |
| **7** | Placeholders and papercuts | F13–F18 | TODO ← **next** |

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

### F21 · Phase 0 breaking changes — `DONE`
Backend security work in flight. When it lands: `POST /trips` stops accepting `created_by`
(remove it from `NewTrip.jsx`), `GET /trips` loses `?email=` and returns only your own trips
(update `getTrips` and `MyTrips.jsx`), and `joinTrip(id)` becomes `joinTrip(id, inviteCode)`.

**Done 2026-11-14.** Phase 0 landed with the 2026-10-19 merge of `origin/main`, and only the
third change was breaking: `POST /trips/{id}/join` now requires `{ invite_code }`, so every
guest join answered 422 until `JoinTrip.jsx` passed the code it already reads from the URL.
The other two were silently ignored by the server — `created_by` and `?email=` are removed
anyway, the latter because it put the user's email in every request URL and server log.

### F3 · Three screens don't exist — `DONE`
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

**F3a done — `/trips/:tripId/planning`.** Built to the Stitch "Generating Your Trip Pitch" screen:
volt icon, progress bar, and a fixed-height 4-row feed where older steps dissolve into a top mask
rather than the list growing. `lib/planningSteps.js` mirrors the backend's `NODE_PROGRESS_MAP`;
progress is **monotonic** because the graph loops back on budget pressure and fairness failure, and
a bar that runs backwards reads as a bug. On `HITL_REQUIRED` the card is replaced by the Stitch
"Curated Destinations" grid — no sidebar, no refresh, per Vignesh. Cards carry a match % normalised
against the top candidate, `llm_reasoning` as the description, cost level, and nearest airport; the
dataset has no imagery so each destination type gets its own gradient. Selecting posts
`/confirm-city` and the *same* stream carries on. `TRIP_COMPLETE` shows the pitch; `ERROR` shows the
backend message with a route back to the lobby. The lobby now redirects everyone into planning when
the trip status moves, so non-leaders follow the run too.

**F3b done — the trip hub.** Built from the Stitch "Trip Hub Overview" and "Itinerary View
(Integrated Bento Timeline)" screens. `TripHubLayout` fetches `GET /result` once and shares it with
every tab through the router outlet, so tab switches re-render rather than refetch. Overview: trip
pitch, squad with per-member flights, hotel, quick stats, Trip Vibe, and the real
`constraint_satisfaction` sentences. Itinerary: day pills, day banner, the schedule woven with the
route legs, a stylised route map, day summary, and the refinement box.

**Deliberate departures from the mock**, all forced by what the payload actually holds:
- *No per-activity prose or "Why SquadPicked" quotes* — the payload has neither; cards show
  rating, address and tags instead of invented copy.
- *`$`/`$$`/`$$$` rather than amounts* — activities carry `price_level` (0–4), not a price.
- *Ranked bars, not a radar, for Trip Vibe* — the reader's job is comparing magnitudes, which a
  radar does poorly (misleading area, shape depends on axis order). On a dark card because the
  brand volt measures **1.21** contrast on white and **14.77** on slate-900; every bar is
  direct-labelled so the value never depends on reading the fill.
- ~~*A stylised route sketch, not a real map*~~ — superseded: the itinerary now has a real
  Leaflet map on OpenStreetMap tiles with numbered pins and directions links.
- *Flights / Lodging / Budget tabs are drawn but inert* — hiding them would misrepresent the page.
- *Squad Upvotes, Est. Steps, Savings Goal and Next Up are omitted* — features that don't exist.

**Dropped by decision:** the mock's three footer tiles (Best Price / Squad Match / Dates) — two of
the three cannot be known until the run is nearly over.

---

## Phase 5 — Guest invite flow

### F4 · `/join/:code` doesn't exist — `DONE`
`TripLobby.jsx:43` and `:179` copy `${origin}/join/${invite_code}`. No route, no page — every
invitee lands on a blank screen.

Backend is ready (`GET /trips/by-invite/{code}` public, `POST /trips/{id}/join` auth'd). Needed:
the route, and a post-auth redirect in `Auth.jsx` — unauthenticated guests stash the code in
`sessionStorage.pendingInvite`, sign in, and resume.

**Done when:** an invitee opens the emailed link, signs in, and lands in the lobby as `joined`.

**Done.** `pages/JoinTrip.jsx` at `/join/:inviteCode`, deliberately outside `ProtectedRoute` since
invitees arrive signed out. Four branches: bad code, signed out (sign-in CTA), signed in and not a
member (join → preferences), already a member (→ lobby). The code is stashed in `sessionStorage`
on arrival and consumed by `Auth.jsx` after **both** the email and Google paths — both previously
hardcoded `navigate("/")`, which would have dropped the invite.

**Known gap (backend):** `POST /join` is permissive — any authenticated user holding the link
joins, with no check against `invited_emails`. An invite link is effectively a bearer token.

---

## Phase 6 — Architecture debt

### F9 · `sessionStorage` carries trip identity — `DONE`
Preferences and the lobby now read `:tripId` from the route; the bare `/trips/lobby` route is gone
since every caller passes an id. Only `NewTrip` → `InvitesSent` still hands off via sessionStorage.
`NewTrip.jsx:35`, `InvitesSent.jsx:13`, `TripPreferences.jsx:53`, `TripLobby.jsx:17`. Dies in a new
tab and makes URLs unshareable — fatal for an invite-based app. `/trips/:tripId/lobby` already
exists; `/trips/preferences` needs a `:tripId` too. Note `pendingInvite` (F4) is a legitimate use.

### F10 · React Query installed, provided, never used — `DONE`
`TripPreferences` (mutation) and `TripLobby` (query + two mutations) are converted, including the
state-keyed `refetchInterval`. `MyTrips`, `InvitesSent` and `authStore` still hand-roll
`useEffect` + loading flags.

### F11 · Two competing user stores — `DONE`
`UserProvider` is mounted in `main.jsx` and never consumed; `authStore` is real. Delete it, plus
empty `store/index.js` and `components/templates/index.js`.

### F12 · `RootLayout` and `SideMenu` are orphaned — `DONE`
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

### F16 · Registration errors always show the wrong message — `DONE`
`Auth.jsx:33` checks `err.message?.includes("409")`, but `apiFetch` throws `body.detail` and never
the status code — duplicate signups read "Invalid email or password."

**Done.** `apiFetch` now attaches the HTTP status to the thrown error, so callers can branch on it
without string-matching a message written for humans, and `Auth.jsx` surfaces the backend's
`detail` verbatim instead of flattening every failure to one guess. Verified live: register returns
`409 {"detail":"Email already registered"}` and login `401 {"detail":"Invalid email or password"}`.

Also fixed in passing: `apiFetch` assumed `detail` is always a string, but the refinements endpoint
returns `{message, code}`, which would have rendered as "[object Object]".

### F17 · Two design systems for one component — `TODO`
antd + a full `ConfigProvider` override for a single `RangePicker`, while unused shadcn
`date-picker` / `calendar` sit in `components/ui/`. `dayjs` is imported but not in `package.json` —
it resolves only transitively through antd. (Note: the contract requires a *range* picker, so
antd may be worth keeping — decide rather than drift.)

### F18 · Minor — `DONE`
`alert()` at `NewTrip.jsx:41` while `sonner` is used everywhere else. Hardcoded
`googleusercontent.com` avatar and inline `dangerouslySetInnerHTML` CSS in `Auth.jsx`.

**Done 2026-11-16.** `NewTrip.jsx` shows a `sonner` toast carrying the server's `detail`
instead of a fixed message in a blocking `alert()`. `Auth.jsx`'s inline `<style>` only
duplicated `glass-card` and `volt-glow` from `index.css` — with light-mode colours hardcoded,
so the page ignored the dark theme — and is gone; its one unique rule (stretching Google's
button iframe) moved to `index.css`. The testimonial avatar was a temporary Stitch export URL
and is now an initials badge.

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

- **2026-11-16** — **F18 done.** `alert()` in `NewTrip.jsx` replaced by a toast; inline CSS and
  the hotlinked avatar removed from `Auth.jsx`. Lint (no new warnings) and build clean.
- **2026-11-14** — **F21 done: guest invites work again.** The Phase 0 merge made
  `POST /trips/{id}/join` require the invite code in the body; the frontend sent no body, so
  every join from `/join/:code` failed with a 422 the backend suite could not see. `joinTrip`
  now takes `(id, inviteCode)`. Also dropped `created_by` from trip creation and `?email=` from
  the trips list — both ignored server-side. F3 marked done; its screens shipped in September.
- **2026-09-23** — **One `items` array per day; name matching gone.** A day was three parallel
  lists — `schedule` (the clock), `activities` (place records), `meals` (prose) — with no key
  joining them, so the UI re-joined them by matching names. That is what let a meal note reading
  "Lunch at California Academy of Sciences" claim the museum.
  `route_stops` was already the resolved ordered join, carrying `place_id`, coordinates and
  address for activities, meals and the hotel alike — including places resolved by text lookup
  that never reached `activities`. `utils/itinerary_items.py` merges the richer fields
  (category, rating, tags) onto it and attaches each route leg to the stop it departs from.
  Derived on read, so nothing needs migrating.
  **Every item carries place data — 233/233 across 35 days.** Meals are now real named
  restaurants with coordinates ("Doppio Coffee & Brunch") rather than the word "Breakfast", so
  they get map pins, photos and directions like anything else. Photography moved onto items, so
  meals key on a real `place_id` instead of a venue name.
  Trips generated before `route_stops` existed (23 of 58 days) have no `items` and fall through
  to the old matcher unchanged.
- **2026-09-21** — **F16 done: auth errors tell the truth.** Registering with an existing email
  said "Invalid email or password", sending users to reset a password for an account they were
  trying to create.
- **2026-09-21** — **Phase 6 done: architecture debt cleared.**
  **F9** — the last sessionStorage handoff is gone; `NewTrip` navigates to
  `/trips/:tripId/invites-sent` and the id travels in the URL. The only remaining use is
  `pendingInvite` in the join flow, which is a legitimate one (it must survive a redirect
  through login).
  **F10** — `InvitesSent` converted to React Query, with the countdown extracted into a
  `useCountdown` hook. No hand-rolled fetching left in the app.
  **F11** — deleted `UserProvider` (mounted in `main.jsx`, never consumed) and the two empty
  index files.
  **F12** — deleted `RootLayout`, `PageLayout`, `SideMenu` and `components/ui/sidebar.jsx`. No
  route mounted any of them and the chain was entirely self-contained; `sidebar.jsx` is
  shadcn-generated and can be re-added with `npx shadcn add sidebar` if a sidebar is ever wanted.
  Also cleared every remaining lint error — unused `React` namespace imports in four shadcn `ui`
  files (unnecessary under the new JSX transform), an unused icon import, and an empty catch.
  **Lint is now fully green (0 errors)**, so a new error is visible rather than lost in noise.
- **2026-09-21** — **F4 done: the guest invite flow.** `/join/:inviteCode` is public, previews the
  trip before you commit to it, and survives the round trip through login. Phase 5 complete — the
  multi-user premise now works end to end.
- **2026-09-11** — **Quick Stats rebuilt around the individual.** Every figure on the card was a
  group aggregate — "Avg / Person" is a number nobody pays, and the combined-budget bar mixes a
  $5,000 budget with a $1,355 one into a meaningless denominator. It now leads with *your* cost
  against *your* budget (matched by `member_id`, derived from the email local part the same way
  `squad.py` does it), falling back to the group view for anyone not on the trip.
  **Removed a misleading metric:** the pink tile rendered `mean(fairness_scores) * 100` as
  "Cost Fairness 17%". Those scores are budget *utilisation* per member, where lower is better —
  so the label inverted the polarity, and averaging destroyed the only thing fairness measures
  (the gap between members: three people at 60% is fair, one at 10% and one at 90% averages the
  same and is not). Replaced with the squad **range** (`8–29% of budget`) plus the backend's own
  `fairness_passed` verdict. `averageScore()` deleted so nothing reaches for it again.
  *Latent, not visible — every current trip lands under budget, so that branch never rendered.*
- **2026-09-08** — **Hub revisions to match the mockups.** Trip Vibe is now the design's radar
  *plus* ranked bars — the radar carries the shape, the bars carry the numbers, since radar area
  cannot be read accurately; both are labelled, which is what the brand volt's 1.21 contrast on a
  white card requires. Squad panel rebuilt to the design (rounded-square avatar, confirmation
  badge, name + role, right-hand pill — carrying flight cost, since every member of a completed
  trip is confirmed by definition). Overview is now the design's bento grid and the long pitch
  paragraph is gone.
  **Font bug found:** `tailwind.config.js` declares `sans: ["Inter", ...]` and every mockup is
  drawn in Inter, but only Geist was ever imported — so `font-sans` silently fell back to
  `system-ui`. Inter is now imported, which is why the app suddenly matches the designs.
- **2026-09-08** — **F3b done: the trip hub.** New `TripHubLayout` template + `pages/hub/{Overview,
  Itinerary}`, organisms (`TripHero`, `TripTabs`, `DayTimeline`, `DayRouteMap`, `DaySummary`,
  `SquadPanel`, `TripStats`, `TripVibe`, `RefinementBox`), molecules (`DayPills`, `TimelineItem`,
  `TransitConnector`, `StatTile`), `lib/itinerary.js` for the derived numbers and `useTripResult`.
  Backend: `GET /result` now returns `trip_name` and a `destination_image` resolved by name, so
  trips completed before photography existed still get a hero banner.
  Two bugs caught by checking the helpers against a real completed trip rather than assuming:
  route legs connect consecutive *activities*, not schedule rows (indexing by row attributed a
  20-minute walk to breakfast), and `constraint_satisfaction` is
  `{passed, satisfied[], unmet[], warnings[]}`, not a map of booleans.
- **2026-09-08** — **Image cache TTL bug + the image-finder script.** The destination image cache
  was in the shared `api_cache`, which carries a collection-wide TTL index (`cached_at`, 86400s)
  for the Places/SerpAPI caches — so every resolved photo was silently deleted after 24 hours and
  all 480 were re-resolved daily. Moved to a dedicated `destination_images` collection with no
  TTL; re-warmed to 467/480. Added `scripts/find_missing_destination_images.py` for the remaining
  13: Claude with server-side web search, `allowed_domains` limited to reuse-permitting sources,
  every URL verified as a real image before it is kept, then downloaded (Unsplash excepted — their
  guidelines require hotlinking, so those are stored as URLs, which the manual override now
  supports). **Blocked on Anthropic API quota until 2026-10-01** — the pipeline is verified except
  the model call itself.
- **2026-09-08** — **Photos on existing trips, and no more loading screen for a shortlist that
  already exists.** Candidates are frozen into the LangGraph checkpoint at scoring time, so trips
  scored before photography existed had none — and backfilling the stored copy does not stick,
  because the checkpoint is rewritten on each resume. Fixed by enriching on the way *out*
  (`utils/candidates.py`): dataset fields are refilled from `destinations.json` by id and images
  attached from the Mongo cache, so old and new trips take the same path at no real cost.
  `GET /trips/{id}` now also returns `candidate_destinations` while a trip is parked on the city
  choice, so the planning page renders the shortlist immediately rather than showing progress while
  SSE replays it, and My Trips routes cards straight to `/planning` instead of bouncing through
  the lobby.
- **2026-09-07** — **Manual photo overrides for the 13 Wikipedia can't cover.** Drop a file named
  `<destination id>.jpg` into `backend/data/destination_images/` and it wins over any automatic
  lookup — no code or config to edit. Served statically by the backend; optional attribution via
  `_credits.json`. `backend/data/destination_images/README.md` documents the process and carries
  the generated list of what is still needed.
  Verified coverage is **467/480 (97.3%)** after re-checking the misses individually — the earlier
  count included one throttling false-negative (Skaneateles). Of the 13 remaining, none are
  imaginary: 5 are real regions Wikipedia files under another title (Long Island AVA, Catalina
  Foothills…), 4 have articles with no lead photo, and 4 have ambiguous titles. A search-based
  fallback was tried and **rejected** — it returned *Pope John VI* for "St. John" and a
  UFO-abduction article for "White Mountains". Confidently wrong beats nothing, so those keep
  their gradients.
- **2026-09-06** — **Destination photography.** Real photos of each destination, resolved on demand
  and cached in Mongo's existing `api_cache` so one lookup serves every later squad — the 480
  destinations are a fixed shared set, so the cache warms fast.
  **Not Google Places**, despite its coverage: under the Maps Platform terms photos have no caching
  exception at all (neither bytes nor photo name may be stored, and the name expires), so every
  render would be billable and the shared-cache design is disallowed. Wikipedia is keyed to the
  *named place*, so it returns the actual location rather than something that merely matches a
  search term, and Commons content is CC-licensed for reuse — so it may be cached. Unsplash sits
  behind it as a fallback (URL cached only, never the file, per their hotlinking rule).
  **Measured coverage: 466/480 = 97%**, 100% for major cities, national parks, mountain towns and
  state parks. The 14 misses are mostly invented region names in the dataset ("Long Island Wine
  Country", "Tucson Foothills") and fall back to the type gradients. Two traps found while
  measuring: Wikimedia 403s any User-Agent without a contactable identifier, and throttling reads
  as "no image exists" unless you back off — an early run reported a false 51%.
- **2026-09-05** — **Fixed "Called get_config outside of a runnable context".** Root cause was
  **Python 3.10**: LangGraph needs 3.11+ to set the runnable-config contextvar in async code
  (`_runnable.py` falls back to a bare `await` when `asyncio.create_task(..., context=)` is
  unavailable), so `interrupt()` could not read its config. `langgraph/config.py` tries to raise a
  clear "Python 3.11 or later required" and then catches its own error, which is why the message was
  so opaque. The mandated `backend/venv` did not exist, so the server was running Anaconda's 3.10 —
  created it on **Python 3.12.6**. Also stopped a failed run's `error` sticking to the trip document.
- **2026-09-05** — **Trip deletion + destination details.** Leader-only
  `DELETE /trips/{id}` which also clears the LangGraph checkpoints for that thread (otherwise a
  paused graph outlives its trip); two-step delete confirm on the My Trips cards; `MyTrips` moved
  onto React Query. `View Details` opens a destination panel — reasoning, best-for tags, vibe
  breakdown and every nearby airport with drive times, using `best_for` / `vibe_tags` / `notes` now
  carried through in the candidate payload. **Not an itinerary:** the graph pauses before flights,
  hotels and activities are fetched, so building one per candidate would mean five full pipeline
  runs per trip.
- **2026-09-05** — **F3a done: the planning + HITL screen.** `pages/Planning.jsx`,
  `molecules/PlanningFeed`, `molecules/DestinationCard`, `lib/planningSteps.js`, and the
  `/trips/:tripId/planning` route; the lobby redirects into it once a run starts. Built from the
  Stitch project's "Generating Your Trip Pitch" and "Curated Destinations" screens.
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
