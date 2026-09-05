# Frontend Tasks — SquadPlanner AI

Working backlog for `frontend/`. The backend agent (LangGraph) is mature; this app is the
product shell being built around it. **Right now no path in this app can plan a trip** — the
funnel stops at the lobby. This doc tracks closing that gap, in order.

Scope: `frontend/` only. The `showcase/` folder is a temporary demo and is out of scope.

**Status:** `TODO` · `IN PROGRESS` · `DONE` · `BLOCKED` · `DROPPED`
**Last updated:** 2026-09-04

---

## Execution Order

| Phase | Goal | Tasks | Status |
|---|---|---|---|
| **1** | Get the payload shape right before building the submit path | F5, F6, F8, F7 | **DONE** |
| **2** | Wire the funnel into the agent | F1, F2, F3 | TODO |
| **3** | Make invites actually work | F4 | TODO |
| **4** | Architecture debt (carried along with phases 2–3, not after) | F9, F10, F11, F12 | TODO |
| **5** | Placeholders and papercuts | F13–F18 | TODO |

Rationale for this order: Phase 1 is cheap, self-contained, and defines the request body that
Phase 2 has to send — doing it second would mean writing the submit call twice. Phase 3 is
independent and can run in parallel. Phase 4 items are picked up inside the phases that touch
those files rather than as a separate cleanup pass.

---

## Decisions

Recorded so they don't get re-litigated. Each names the task that implements it.

### D1 · `created_by` holds the user `_id`, with `created_by_email` alongside — *implement in F2*
It currently holds the **email** (`NewTrip.jsx:31`). Email is mutable — change it, or sign up local
then sign in with Google under a different address, and every trip you created orphans. `_id` is the
`users` primary key and the JWT `sub`, so it is the only stable handle.

`created_by_email` is denormalized next to it because the invite model is email-keyed by necessity
(you invite people who have no account yet), so the leader↔member join stays a string compare
instead of a users lookup on every read.

Migration: `list_trips` queries `{"created_by": email}` and `MyTrips.jsx` passes `user.email` —
both change with it. Existing trip docs need a backfill or a wipe.

### D2 · The server decides who the leader is, not the client — *implement in F2*
`GET /api/trips/{id}` returns a computed `viewer_is_leader`, not raw `created_by`. The server
already knows who is asking via the JWT cookie; a gate the client derives is a gate the client can
flip; and it avoids handing the creator's email to every invitee.

Requires `Depends(get_current_user)` on the trip endpoints. **`get_trip` is unauthenticated today** —
anyone holding a trip ID can read the full squad roster.

### D3 · `is_leader` is derived server-side when assembling `members` — *implement in F2*
`agent/nodes/input_parser.py:57` requires exactly one `is_leader=True` or the graph raises at the
first node. Deriving it from `created_by` and ignoring the client's value closes both failure modes:
zero leaders (the leader never submitted) and two leaders (client bug or tampering). The field stays
in the payload because `MemberInput` requires it — the client just isn't trusted on it.

For reference, that validation is the *only* functional use of `is_leader` in the backend. Every
other occurrence is a docstring example or test fixture; no node branches on it. Note also that
`POST /trips/{id}/confirm-city` has no auth check at all, so `is_leader` is not a security boundary.

### D4 · Readiness counts only `accepted` members — *implement in F2*
Otherwise one unresponsive invitee blocks the trip forever. The leader can remove a pending member.

---

## Phase 1 — Payload correctness

### F5 · Preference keys don't match the backend — `DONE`
`TripPreferences.jsx:10` defines six vibes: `nightlife, adventure, shopping, food, urban, nature`.
The backend uses exactly five (`backend/data/destinations.json` → `vibe_tags`):
**`nightlife, shopping, food, urban, outdoor`**.

- `adventure` and `nature` do not exist backend-side and are silently ignored.
- `outdoor` is never collected — the key that drives national-park scoring across 480 destinations.

**Done when:** the slider set emits exactly the five backend keys.

**Done:** `TripPreferences.jsx:12` now lists the five backend keys; `adventure` + `nature` collapsed
into `outdoor`, keeping the "Nature & Outdoors" label. Six sliders became five.

### F6 · Slider scale is off by 100× — `DONE`
Sliders emit `0–100`; `preference_vector` values are `0.0–1.0`
(see `backend/tests/demo_input_cases.json`). Normalize on submit, keep 0–100 in the UI.

**Done when:** the built payload contains floats in `0.0–1.0`.

**Done:** `normalizePreferenceVector()` in `src/lib/tripPayload.js`. The slider is `step={25}`, so
values land on exactly 0.0 / 0.25 / 0.5 / 0.75 / 1.0.

### F8 · `food_restrictions` has no input — `DONE`
The itinerary validator checks vegan / gluten-free / halal / vegetarian, but the UI offers only a
free-text Notes box. Notes maps correctly to `preference_notes`; `food_restrictions` is uncollected.

**Done when:** a multi-select emits `food_restrictions: string[]`.

**Done:** toggle chips in the Personal Notes card, limited to the four the itinerary validator
actually checks (`DIETARY_OPTIONS`). Anything else would be dead weight downstream.

### F7 · Multiple date windows vs. a single trip date — `DONE` (deferred by design)
`TripPreferences.jsx` collects a *list* of ranges per member. `TripState` has one `start_date` /
`end_date`, and nothing anywhere intersects windows into a single range.

**Decision:** don't resolve it here. The member payload carries the full
`availability: [{start_date, end_date}, ...]` array, which is strictly more information than a
single range. Reconciling N members into one range can only happen once everyone has submitted —
i.e. at start-planning time — so the strategy (backend computes the overlap vs. leader confirms in
the lobby) is decided as part of **F2**, not here. No longer blocks F1.

> **Not a bug — do not "fix":** `AirportSelect` returns the IATA code (`"ORD"`), which is exactly
> what the backend's `origin_city` expects.

---

## Phase 2 — Wire the funnel into the agent

### F1 · Preferences are collected and thrown away — `TODO` · **next**
`TripPreferences.jsx:58` — `handleSubmit` now builds the correct payload via `buildMemberPayload()`
but only `console.debug`s it (marked `TODO(F1)`). Still needs the backend endpoint
(`POST /api/trips/{id}/preferences`), which does not exist.

Two things land with this task:
- `is_leader` is hardcoded `false`. The honest check is `user.email === trip.created_by`, which
  needs the trip fetch this task adds anyway.
- The F7 date-window resolution strategy (see above).

**Done when:** preferences persist and survive a reload.

### F2 · The lobby is a terminal dead end — `TODO`
`TripLobby.jsx` has no "Start planning" action. Nothing in the app ever calls
`GET /api/trips/{id}/stream`, so the agent is never invoked.

**Requirement:** the *Scout Destinations* button is visible only to the leader, and only once every
member has submitted preferences.

Implements D1–D4. Two gaps block the readiness check:

- **The creator is not in the member list.** `create_trip` builds `invited_members` from
  `invited_emails` only, so "all invited members submitted" can pass while the leader has not —
  and then the graph dies with zero leaders. Fix: insert the creator at creation with
  `status: "accepted"`.
- **There is no per-member submitted flag** — that arrives with F1. The check is then
  `invited_members.every(m => m.preferences_submitted)` over accepted members (D4).

Also settles the F7 date-window resolution strategy, and computing readiness server-side closes F15.

**Done when:** the leader can start a run from the lobby once the squad is ready, and nobody else
can see the button.

### F3 · Three screens don't exist — `TODO`
No SSE/streaming progress page, no HITL city-selection screen, no itinerary view — the entire
second half of the product. `TripPreferences.jsx:57` also falls back to `navigate("/dashboard")`,
a route not in the router (`Dashboard.jsx` is a one-line stub) → blank screen.

**Done when:** a trip runs end to end: stream → pick a city → see the itinerary.

---

## Phase 3 — Invites

### F4 · `/join/:code` doesn't exist — `TODO`
`TripLobby.jsx:41` and `:186` copy `${origin}/join/${invite_code}` to the clipboard. There is no
route, no page, and no backend handler. Every invited member who clicks the emailed link gets a
blank page — which kills the multi-user premise the app is built on.

**Done when:** an invitee can open the link, sign in, and land in the lobby as an accepted member.

---

## Phase 4 — Architecture debt

### F9 · `sessionStorage` carries trip identity — `TODO`
Used across `NewTrip.jsx:35`, `InvitesSent.jsx:13`, `TripPreferences.jsx:53`, `TripLobby.jsx:17`.
Dies in a new tab and makes every URL unshareable — fatal for an invite-based app.
`/trips/:tripId/lobby` already exists in the router.

### F10 · React Query is installed, provided, and never used — `TODO`
Every page is hand-rolled `useEffect` + `useState` + manual loading flags, and `TripLobby.jsx:36`
polls with a raw 5s `setInterval`. The lobby is exactly the refetch case React Query exists for.

### F11 · Two competing user stores — `TODO`
`UserProvider` is mounted in `main.jsx` and never consumed; `authStore` is the real one.
Delete `UserProvider`, plus empty `store/index.js` and `components/templates/index.js`.

### F12 · `RootLayout` and `SideMenu` are orphaned — `TODO`
No route mounts them (the router uses `HomeLayout` and `TripFlowLayout`). `SideMenu` also hardcodes
`"Vignesh"` / `"@vignesh"`. Adopt or delete — currently a trap for anyone editing nav.

---

## Phase 5 — Placeholders and papercuts

### F13 · `Home.jsx` is 100% fake — `TODO`
Hardcoded "Vignesh", "140 Miles Traveled", "PARIS, FRANCE", "$864", and a `EuropeMap` for a
**US-only** dataset. It is the post-login landing page.

### F14 · Five dead nav links — `TODO`
`HomeHeader`: Explore / Shared Trips / Stats. `SideMenu`: Help. Plus `/settings`. None are routed.
No 404 route and no error boundary either.

### F15 · Hardcoded readiness — `TODO` · *closed by F2*
`TripLobby.jsx:68` sets `readiness = 60` while `readyMembers` / `totalMembers` are computed two
lines above and never used.

### F16 · Registration errors always show the wrong message — `TODO`
`Auth.jsx:33` checks `err.message?.includes("409")`, but `apiFetch` throws `body.detail`
("Email already registered") and never the status code — so duplicate signups read
"Invalid email or password."

### F17 · Two design systems for one component — `TODO`
antd + a full `ConfigProvider` theme override for a single `RangePicker`, while unused shadcn
`date-picker` / `calendar` sit in `components/ui/`. `dayjs` is imported in `TripPreferences` but
is not in `package.json` — it resolves only transitively through antd.

### F18 · Minor — `TODO`
`alert()` at `NewTrip.jsx:41` while `sonner` toasts are used everywhere else. Hardcoded
`googleusercontent.com` testimonial avatar and inline `dangerouslySetInnerHTML` CSS in `Auth.jsx`.

---

## Changelog

- **2026-09-04** — Recorded decisions D1–D4 (`created_by` → `_id`, server-computed
  `viewer_is_leader`, server-derived `is_leader`, readiness counts accepted members only) and
  folded the leader-only *Scout Destinations* gate into F2.
- **2026-09-04** — **Phase 1 complete (F5, F6, F8, F7).** Added `src/lib/tripPayload.js` with a pure
  `buildMemberPayload()`; fixed the preference keys and 0–100 → 0.0–1.0 scale; added dietary
  toggle chips; folded the orphaned "Carry-on Only" toggle into `preference_notes` (the backend
  has no field for it, and the constraint extractor reads free text). `handleSubmit` builds the
  payload but does not yet send it — that's F1. Lint clean, build passes.
- **2026-09-04** — Backlog created from a full frontend review.
