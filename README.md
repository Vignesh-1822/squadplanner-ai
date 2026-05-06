# SquadPlanner AI

SquadPlanner AI is a full-stack group trip planning prototype. A group submits dates,
origin airports, budgets, dietary restrictions, numeric travel preferences, and optional
natural-language notes. The backend runs a LangGraph planning workflow that scores US
destinations, pauses for leader destination approval, fetches live travel context, builds
a day-by-day itinerary, checks constraints and fairness, then streams progress and the
final plan over Server-Sent Events. After generation, the leader can also ask for
natural-language refinements such as "Make Day 2 cheaper" or "Swap the museum for something
outdoors"; the backend parses the edit, re-enters the LangGraph checkpoint at the affected
node, reruns only the downstream subgraph, and streams the updated itinerary back to the UI.

Temporary live demo: https://ai-squad-planner-v2-0.vercel.app/

The project now has three major pieces:

- `backend/`: the working FastAPI + LangGraph planning API, debug UI, HITL flow, persistence,
  streaming, integrations, tests, and LangSmith wiring.
- `showcase/`: the deployable product app used by the hosted demo. It creates trips against the
  live backend, streams graph progress, handles destination approval, and renders completed
  itineraries with maps.
- `frontend/`: the original design-system shell and product direction work. It has polished
  dashboard/new-trip/preference screens, but the showcase app is the frontend that is currently
  aligned to the backend API.

## What Has Been Built

### Backend agent workflow

- FastAPI app with CORS, `/health`, `/debug`, trip routes, HITL routes, refinement routes, and admin routes.
- LangGraph orchestrator in `backend/agent/graph.py`.
- MongoDB-backed checkpointing for Human-in-the-Loop graph pause/resume.
- Optional LangSmith tracing through `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, and
  `LANGCHAIN_PROJECT`.
- LLM provider switch for Anthropic or Groq through `LLM_PROVIDER`.
- Natural-language preference extraction for group/member notes.
- Destination scoring against `backend/data/destinations.json`.
- Destination shortlist generation with five candidate destinations and LLM reasoning.
- HITL city selection at `city_selection_hitl`.
- Dynamic tool selection based on group preference vector and hard constraints.
- Parallel fetch step for flights, activities, and weather.
- Budget analysis and destination retry routing for severe budget pressure.
- Hotel search with retry support after fairness failure.
- Itinerary subgraph with clustering, LLM day planning, flight-time alignment, route planning,
  feasibility checks, deterministic validation, and rebuild loops.
- Fairness and compatibility scoring.
- Final trip pitch generation.
- Stateful post-generation refinement. Natural-language edits are normalized, stored in graph
  state, routed to the correct completed node via LangGraph checkpoint state, and streamed as an
  incremental rerun.
- SSE event streaming for node progress, city-selection pause, refinement updates, completion,
  and errors.

### External tool wrappers

- SerpAPI flights and hotels with a monthly hard limit gate and MongoDB cache.
- Google Places activity fetching by category with MongoDB cache.
- Google Routes day-route planning.
- Open-Meteo weather lookup with no API key required.
- Estimated fallback results when live APIs fail or quota is exhausted.

### Constraint handling

- Natural-language notes are preserved in API input and initial graph state.
- Hard avoids like "no clubs" filter activity categories and fetched activities.
- Schedule constraints such as no early non-breakfast activities are extracted and validated.
- Dietary restrictions including vegan, gluten-free, halal, and vegetarian are checked by the
  itinerary validator.
- Required cuisines and relaxed-pace requirements are represented in constraint satisfaction.
- Final output includes `preference_constraints`, `constraint_satisfaction`, itinerary days,
  rationale, and constraint notes.

### API surface

- `POST /trips` creates a trip and stores initial graph state.
- `GET /trips/{trip_id}` returns the stored trip document.
- `GET /trips/{trip_id}/stream` streams graph progress and final output.
- `POST /trips/{trip_id}/confirm-city` resumes the graph after destination selection.
- `POST /trips/{trip_id}/refine` queues a post-generation natural-language refinement.
- `GET /trips/{trip_id}/refinements/{refinement_id}/stream` streams refinement progress and
  the updated itinerary.
- `GET /admin/serpapi-usage` returns current SerpAPI monthly usage.
- `GET /health` returns a simple liveness response.
- `/debug` serves a local manual testing UI.

### Testing and demo assets

- `backend/docs/TESTING_PLAYBOOK.md` documents the manual and automated test flow.
- `backend/tests/demo_input_cases.json` contains copy-paste demo payloads for the debug UI.
- `backend/tests/manual_cases.json` contains structured manual API cases.
- Deterministic regression tests cover destination scoring, graph wiring, and preference constraints.
- Live full-graph integration testing is gated by `RUN_LIVE_INTEGRATION=true` to avoid accidental
  LLM/tool quota spend.
- Live integration artifacts are written to `backend/tests/artifacts/`.

### Frontend

- `showcase/` React 18 + Vite product app connected to the backend.
- Trip input form with editable dates, group notes, travelers, leader selection, origin airports,
  budgets, dietary restrictions, preference notes, and five preference sliders.
- Demo payload defaults in `showcase/src/demoTrip.js` for a polished end-to-end demo.
- Live planning page using `EventSource` against `GET /trips/{trip_id}/stream`.
- Candidate destination cards for the HITL city-selection pause.
- `POST /trips/{trip_id}/confirm-city` integration for destination approval.
- Completed itinerary page that loads stored/final trip output, displays trip pitch, travelers,
  flights, hotel, day tabs, agenda, fairness/compatibility scores, and constraint notes.
- Completed itinerary page includes a refinement form that opens an SSE stream and replaces the
  itinerary with the updated graph result.
- Interactive Leaflet/OpenStreetMap itinerary map with markers and route polylines.
- LocalStorage caching of completed trip payloads for smoother reloads.
- Vercel-ready SPA config in `showcase/vercel.json`.
- Original `frontend/` React 18 + Vite app scaffold.
- Tailwind/shadcn-style component structure with atoms, molecules, organisms, templates, and layouts.
- Home dashboard-style page, new-trip screen, trip-preferences screen, and placeholder dashboard route.
- React Router and TanStack Query providers are wired.
- Basic API helper exists in `frontend/src/services`, but that original app is not fully aligned
  with the backend yet.

## Current Architecture

```text
backend/
  main.py                         FastAPI app, startup, router registration
  config.py                       settings, LLM factory, LangSmith setup
  api/                            trips, HITL, refinement, admin routes
  agent/
    graph.py                      parent LangGraph orchestrator
    state.py                      TripState and ItineraryState schemas
    nodes/                        parse, constraints, refinement, destination, tools, budget, hotel, fairness, output
    subgraphs/itinerary.py        itinerary-planning subgraph
  tools/                          SerpAPI, Google Places, Google Routes, Open-Meteo wrappers
  db/                             MongoDB client, checkpointer, persisted models
  utils/streaming.py              SSE formatting and graph event streaming
  utils/refinement_streaming.py   SSE graph re-entry for post-generation edits
  data/destinations.json          US destination dataset
  tests/                          deterministic and live-gated tests

frontend/
  src/pages/                      home, new trip, trip preferences, dashboard placeholder
  src/components/                 UI building blocks
  src/routes/                     React Router setup
  src/services/                   early API helpers

showcase/
  src/pages/                      trip input, live planning, completed/refinable itinerary
  src/ui/ItineraryMap.jsx         Leaflet/OpenStreetMap route and stop map
  src/api.js                      backend API client and SSE URL helper
  src/storage.js                  local completed-trip cache
  vercel.json                     SPA rewrites for Vercel hosting
```

## Backend Setup

From the repo root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `backend/.env` with:

```env
MONGODB_URI=mongodb+srv://...
ANTHROPIC_API_KEY=...
SERPAPI_KEY=...
GOOGLE_PLACES_API_KEY=...
GOOGLE_ROUTES_API_KEY=...
LLM_PROVIDER=anthropic
SERPAPI_MONTHLY_HARD_LIMIT=200
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=squadplanner
```

Run the backend:

```powershell
python -m uvicorn main:app --reload
```

Useful URLs:

- API health: `http://127.0.0.1:8000/health`
- Debug UI: `http://127.0.0.1:8000/debug`
- API docs: `http://127.0.0.1:8000/docs`

## Frontend Setup

Run the current backend-aligned product app:

```powershell
cd showcase
npm install
npm run dev
```

By default, `showcase/` calls `http://127.0.0.1:8000`. To point it at a hosted backend, create
`showcase/.env.local`:

```env
VITE_API_BASE_URL=https://your-backend.example.com
```

Run the original design-system frontend:

```powershell
cd frontend
npm install
npm run dev
```

The original `frontend/` app currently defaults API calls to `http://localhost:8000/api`, while the
backend routes are mounted at the root, for example `/trips`. Use `showcase/` for the working
backend-connected UI until the original app is reconciled.

## Tests

Run deterministic backend tests from `backend/`:

```powershell
python -m pytest tests/test_destination_selector.py tests/test_preference_constraints.py tests/test_graph_wiring.py tests/test_refinement.py -v
```

Run live full-graph integration only when you intend to spend LLM and API quota:

```powershell
$env:RUN_LIVE_INTEGRATION = "true"
python -m pytest tests/test_integration.py -v -s
```

Use a custom live payload:

```powershell
$env:RUN_LIVE_INTEGRATION = "true"
$env:LIVE_TRIP_INPUT_JSON = '<paste payload JSON>'
python -m pytest tests/test_integration.py -v -s
```

## Manual Backend Flow

1. Start the backend.
2. Open `http://127.0.0.1:8000/debug`.
3. Paste a payload from `backend/tests/demo_input_cases.json`.
4. Create the trip.
5. Start the stream.
6. Choose a candidate destination when `HITL_REQUIRED` appears.
7. Wait for `TRIP_COMPLETE`.
8. In the showcase itinerary page, enter a refinement such as `Make Day 2 cheaper` or
   `Swap the museum for something outdoors`.
9. Watch the refinement SSE events and confirm the itinerary updates in place.

## Deployment

The current hosted demo uses `showcase/` on Vercel and `backend/` on Render. If both services are
connected to this GitHub repository and branch, committing and pushing replaces the old deployed
version automatically.

Commit and push from the repo root:

```powershell
git add backend showcase README.md
git commit -m "Add stateful itinerary refinement endpoint"
git push origin main
```

Vercel frontend settings:

- Root directory: `showcase`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable: `VITE_API_BASE_URL=https://your-render-service.onrender.com`

Render backend settings:

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Required Render environment variables:

```env
MONGODB_URI=
ANTHROPIC_API_KEY=
SERPAPI_KEY=
GOOGLE_PLACES_API_KEY=
GOOGLE_ROUTES_API_KEY=
LLM_PROVIDER=anthropic
SERPAPI_MONTHLY_HARD_LIMIT=200
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=squadplanner
```

After deploy:

1. Confirm Render health: `https://your-render-service.onrender.com/health`.
2. Confirm Vercel has `VITE_API_BASE_URL` pointed at the Render backend.
3. Open the Vercel showcase app, complete a trip, then test the refinement box on the itinerary page.

If auto-deploy is not enabled, push the commit and then click "Redeploy latest commit" in Vercel
and Render.

## What Is Pending

### Backend product features

- Google OAuth and real user identity flow.
- Join-by-invite flow around `invite_code`.
- Member preference submission/update endpoint.
- Trip status endpoint for dashboard polling.
- Past-trip listing endpoint.
- Stronger error recovery and user-facing failure messages.
- DB indexes/TTL setup script or migration checklist for production environments.
- Cleanup of older/unused backend modules under `backend/api/routes` and `backend/agent/tools` if they are no longer part of the active path.

### Frontend integration

- Decide whether `showcase/` becomes the main frontend or gets merged back into `frontend/`.
- Reconcile the original `frontend/` API base URL mismatch (`/api` prefix in frontend helper vs
  root-mounted backend routes).
- Align the original `frontend/` preference keys with backend keys. The backend uses `outdoor`,
  while the current original preference page still includes `adventure` and `nature`.
- Replace placeholder/sample data in the original home and dashboard views with backend data.
- Add invite/join UX and member readiness states.
- Add persistent trip retrieval/listing UI beyond the localStorage cache used by `showcase/`.
- Add loading, error, empty, and completion states.

### Testing and quality

- Add route-level API tests for `POST /trips`, `GET /trips/{id}`, streaming, and city confirmation.
- Add mocked integration tests that do not require live LLM/tool calls.
- Add frontend tests once backend integration begins.
- Run lint/build checks for the frontend and add CI.
- Normalize or replace docs that contain mojibake characters from earlier sessions.
- Keep generated files such as `__pycache__`, `.pyc`, `.pytest_cache`, and `tests/artifacts` out of Git.

### Deployment

- Decide deployment topology for backend, frontend, and MongoDB Atlas.
- Add production environment variable documentation.
- Configure CORS for real frontend origins instead of `*`.
- Decide whether graph execution should remain request/stream-driven or move to a worker queue.
- Enable LangSmith tracing in hosted/demo environments by setting `LANGCHAIN_TRACING_V2=true`,
  `LANGCHAIN_API_KEY`, and `LANGCHAIN_PROJECT`.

## Notes for Future Work

- The backend is the current source of truth for behavior.
- The debug UI is the fastest way to demo the live agent without waiting for frontend integration.
- The live integration test is intentionally opt-in because it can spend Anthropic, SerpAPI, and Google API quota.
- `backend/docs/TESTING_PLAYBOOK.md` is the best companion document for manual testing.
- `backend/docs/squadplanner.md` and `backend/docs/SQUADPLANNER_MODULES_5_8.md` contain useful history/spec context, but some sections are stale now that Modules 5-8 have been implemented.
