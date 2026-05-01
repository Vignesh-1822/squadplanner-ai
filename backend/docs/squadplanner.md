# SquadPlanner — Complete Project Bible

> This document is the single source of truth for SquadPlanner.
> It captures everything: what we're building, why every decision was made,
> what's been built, what's remaining, and how to continue.
> Use it to brainstorm, build, and make architectural decisions without losing context.

---

## What Is SquadPlanner

An AI-powered group trip planning app. A squad of friends inputs their travel preferences —
dates, budgets, and a 5-dimension interest profile (outdoor, food, nightlife, culture, shopping).
An AI agent scores ~500 US destinations, searches for flights and hotels, builds a
day-by-day itinerary, checks fairness across the group, and streams the full plan
back to the group in real time.

**Origin:** Started as a hackathon MVP. Being rebuilt from scratch as a production-quality
portfolio project to demonstrate full-stack AI engineering competence — specifically
LangGraph agent architecture, tool orchestration, HITL workflows, and SSE streaming.

**Primary goal:** A working, demonstrable product that holds up in technical interviews.
Every architectural decision is made with "can I defend this in an interview?" in mind.

---

## Team

- **Manoj** — backend, AI agent, everything in this repo. Owns `/backend` entirely.
- **Teammate** — experienced frontend developer. Owns `/frontend` entirely.
  Do not touch `/frontend`. Do not give frontend advice unless explicitly asked.

---

## Tech Stack — Decided, Non-Negotiable

| Layer | Choice | Why |
|---|---|---|
| Language | Python | Agent ecosystem, Anthropic SDK |
| Framework | FastAPI | Async-native, SSE support, clean DX |
| Agent | LangGraph StateGraph | See architecture section |
| LLM | Claude Haiku 4.5 (Anthropic) | Fast, cheap, good instruction following |
| LLM swap | Groq Llama 3.1 8B | One env var change for free public hosting |
| Database | MongoDB Atlas (Motor async) | Nested trip JSON, no migrations |
| Flights/Hotels | SerpAPI | 200 free calls/month hard limit |
| Activities | Google Places API (New) | 10K free/month |
| Routes | Google Routes API | 10K free/month |
| Weather | Open-Meteo | Free, no key needed |
| Observability | LangSmith | Free tier, traces every node automatically |
| Streaming | SSE via FastAPI StreamingResponse | Simple, frontend-compatible |
| Deployment | Railway | Simple deploys, env var management |

**LLM abstraction:** `get_llm()` in `config.py` reads `LLM_PROVIDER` env var.
- `"anthropic"` → Claude Haiku 4.5
- `"groq"` → Llama 3.1 8B

Swapping providers is literally one line in `.env`. No other code changes.

---

## Why LangGraph — The Full Reasoning

This is the most important architectural decision. Know it cold for interviews.

**What was evaluated:**
1. ReAct agent (tool-calling loop) — rejected
2. Supervisor multi-agent pattern — rejected
3. CrewAI — rejected
4. LangGraph StateGraph — chosen

**Why ReAct was rejected:**
ReAct is a loop of "think → call tool → observe → repeat." It's designed for
open-ended reasoning where the agent decides what to do next. SquadPlanner's
workflow is a *known, fixed sequence* — parse input, score destinations, fetch data,
build itinerary, check fairness. ReAct adds unpredictability to something that
should be deterministic. We'd spend more time constraining it than using it.

**Why Supervisor was rejected:**
A supervisor pattern spins up sub-agents and orchestrates them. Good for
heterogeneous teams of specialized agents. SquadPlanner has one coherent workflow —
adding a supervisor layer means two graphs doing the work of one, more latency,
harder to debug, harder to explain.

**Why CrewAI was rejected:**
Higher-level abstraction, less control. The feedback loops (budget retry, feasibility
swap, validation rebuild) require precise conditional edge wiring. CrewAI doesn't
expose that granularity cleanly. Also: interview answer "I used CrewAI" is weaker
than "I built a StateGraph with conditional edges and HITL checkpointing."

**Why LangGraph StateGraph was chosen:**
- Explicit state schema (TripState TypedDict) — every field defined, no surprises
- Conditional edges = deterministic routing logic, fully testable
- interrupt() for HITL = production pattern, not a hack
- MongoDBCheckpointer = state persists across server restarts
- astream_events() = SSE streaming built in
- Parallel fan-out with asyncio.gather = flights + activities + weather concurrently
- Subgraph pattern = clean encapsulation of the itinerary inner loop
- Interview-friendly: you can draw the graph on a whiteboard and explain every edge

---

## Agent Architecture

### Two-graph system

**Orchestrator (parent graph)** — `agent/graph.py`
Manages the full trip planning pipeline from input to output.
Uses `TripState`.

**Itinerary Agent (subgraph)** — `agent/subgraphs/itinerary.py`
Handles the complex inner loop: neighborhood clustering → LLM itinerary
building → flight time alignment → route planning → feasibility check →
validation. Called as a node inside the orchestrator.
Uses `ItineraryState`. Never imports from `agent/graph.py`.

### Why a subgraph for itinerary?
Encapsulates the feedback loops (feasibility swap, validation rebuild).
Orchestrator stays clean and linear. Subgraph is independently testable
with mock inputs. Defensible in interviews as a real architectural boundary.

### Complete node sequence

```
ORCHESTRATOR:
parse_input
  → select_destination          [LLM call #1: destination reasoning]
  → city_selection_hitl         [HITL interrupt — waits for leader]
  → dynamic_tool_selection
  → parallel_data_fetch         [concurrent: flights + activities + weather]
  → budget_analysis
  → [conditional] severe → select_destination (retry, max 3)
  → [conditional] moderate/ok → search_hotel
  → search_hotel
  → run_itinerary_node          [calls itinerary subgraph]

ITINERARY SUBGRAPH:
  → cluster_by_neighborhood
  → build_itinerary             [LLM call #2: itinerary building]
  → align_flight_times
  → plan_routes
  → [conditional] infeasible → plan_routes (swap, max 2 per day)
  → validation_gate
  → [conditional] errors → build_itinerary (rebuild, max 2)
  → returns to orchestrator

ORCHESTRATOR (continued):
  → compute_fairness
  → [conditional] unfair → search_hotel (retry, max 1)
  → assemble_output             [LLM call #3: trip pitch narrative]
  → END → stream TRIP_COMPLETE via SSE
```

### Feedback loops (4 total)
1. **Severe budget** → retry destination (max 3 attempts)
2. **Route infeasible** → swap activity (max 2 swaps per day)
3. **Validation fails** → rebuild itinerary (max 2 attempts)
4. **Unfair cost split** → find cheaper hotel (max 1 retry)

### LLM calls (exactly 3)
Everything else is deterministic Python.
1. `select_destination` — 1–2 sentence fit explanation per city
2. `build_itinerary` — structured JSON day plans
3. `assemble_output` — 4-paragraph trip pitch narrative

### Key agentic behavior: dynamic tool selection
Group preference vector is averaged across all members.
`dynamic_tool_selection` node only fires Google Places calls for
categories scoring ≥ 0.35. Food is always included regardless of score.
Example: adventure group with nightlife=0.15 → nightlife API call skipped.
This is the clearest example of the agent choosing its own tools based on context —
lead with this in portfolio demos.

---

## Data Model

### 5D Preference Vector
Every member has: `{"outdoor": 0.0–1.0, "food": 0.0–1.0, "nightlife": 0.0–1.0, "culture": 0.0–1.0, "shopping": 0.0–1.0}`
These are floats, not integers. The five keys are fixed — never add or rename.
The group vector is a simple average across all members.

### Destinations Dataset
~500 US destinations in `backend/data/destinations.json`.
Covers: major cities, small towns, national parks, beach towns, mountain towns, islands.
Each destination has:
- `id`, `name`, `type`, `state`
- `lat`, `lng`, `search_radius_km`
- `nearest_airports` (list with IATA codes and drive times)
- `cost_level`: "low" | "medium" | "high"
- `best_for`: list of tag strings
- `vibe_tags`: same 5D structure as member preference vector (floats 0–1)
- `notes`: practical travel notes (parking, car needed, etc.)

**Important:** vibe_tags uses `outdoor` (not `adventure`). This was normalized
when merging the 5 source JSON files. Do not rename it back.

### MongoDB — 3 Collections

**`users`**
One doc per registered user. Stores Google OAuth info and default travel preferences.
Default preferences auto-fill when user joins any trip (they can override per-trip).

**`trips`**
Core collection. One document per trip. Contains:
- `invite_code` — short alphanumeric string used in shareable URLs (not the MongoDB _id)
- `members` array — embedded, not a separate collection
- `status` — drives frontend UI: `waiting_for_preferences → ready_to_generate → generating → city_selection → complete → failed`
- `agent_state` — full TripState saved by LangGraph. Written by agent only, never manually.
- `trip_pitch` — single overwritable object. No versioning. Refinements overwrite it.
- `refinement_history` — string array for UI display only ("Make Day 2 dinner cheaper")

**`api_cache`**
Caches SerpAPI + Google Places results. TTL index on `cached_at`.
Also stores SerpAPI monthly usage counter (`type: "serpapi_usage"`).
Cache key patterns:
- Flights: `flights:{origin}:{dest}:{depart}:{return}:{adults}` (TTL 12h)
- Hotels: `hotels:{dest}:{check_in}:{check_out}:{ceiling}` (TTL 12h)
- Places: `places:{dest}:{category}` (TTL 24h)

### SerpAPI Budget Gate
Hard limit: 200 calls/month (set in env var `SERPAPI_MONTHLY_HARD_LIMIT`).
Before every SerpAPI call: atomic MongoDB `find_one_and_update` with `$lt` guard.
If limit hit: raise `SerpAPILimitReached`, return estimated results with `is_estimated=True`.
Never exceed the limit — no exceptions.

---

## UX Flow (How The App Works)

1. User creates profile (Google OAuth — name, email, avatar)
2. User creates a trip → becomes trip leader → gets a shareable invite link
3. Other users join via the link
4. Every member (leader + all members) submits their preferences:
   - Home airport, total budget, food restrictions
   - 5D preference vector (slider UI)
   - Date windows, preferred trip length
5. Leader sees dashboard: who has/hasn't submitted
6. Once all submitted, leader clicks "Generate Trip"
7. Agent runs → leader sees top 5 city options → picks one (HITL)
8. Agent continues → streams progress to frontend via SSE
9. Output page:
   - Main area: shared itinerary (days, hotel, map)
   - Left sidebar: per-user data (their flight, budget utilization, compatibility score)
10. Leader can refine via chat: "Make Day 2 dinner cheaper" → agent updates and overwrites

---

## V1 Scope — What's In, What's Out

### In V1
- Destination selection from 500-destination database
- Dynamic Google Places for activities
- SerpAPI for flights + hotels
- LLM itinerary building with dynamic day count
- 3 meals per day (breakfast, lunch, dinner)
- Google Maps routes + feasibility checks
- Weather-aware planning
- Fairness scoring across members
- HITL city selection
- SSE streaming progress to frontend
- Iterative refinement via chat
- User accounts (Google OAuth)
- Save/view past trips
- Shareable invite links

### Explicitly NOT in V1
- International destinations
- Real-time collaboration (multiple users editing simultaneously)
- Side-by-side trip comparison
- Export to PDF or calendar
- Booking integration (just planning, no actual booking)
- MCP servers (deferred — not needed for V1 functionality)
- Mobile app

---

## Build Status

### Completed (Modules 1–4)

**Module 1 — Foundation**
`config.py`, `main.py`, `db/client.py`, `db/checkpointer.py`, `db/models.py`
FastAPI starts, MongoDB connects, `/health` returns 200. ✅

**Module 2 — State Schemas**
`agent/state.py` — `TripState` and `ItineraryState` TypedDicts fully defined.
All fields, Annotated accumulator fields, correct types. ✅

**Module 3 — Tool Wrappers**
`tools/serpapi.py` — flights + hotels with budget gate. Tested against real SerpAPI. ✅
`tools/google_places.py` — activity fetch by category with MongoDB cache. ✅
`tools/google_routes.py` — directions between activities. ✅
`tools/open_meteo.py` — weather fetch (no key). ✅

**Module 4 — Orchestrator Nodes**
All 7 nodes built and individually tested:
- `parse_input` ✅
- `select_destination` ✅ (LLM reasoning working, JSON parsing fixed)
- `dynamic_tool_selection` ✅
- `budget_analysis` ✅
- `search_hotel` ✅ (real SerpAPI calls confirmed)
- `compute_fairness` ✅
- `assemble_output` ✅ (4-paragraph LLM output working)

**Destinations dataset**
`backend/data/destinations.json` — all 5 batch files merged, `adventure` renamed to `outdoor`. ✅

**MongoDB Atlas**
Cluster live, 3 collections created, all indexes in place, connection string in `.env`. ✅

### Remaining (Modules 5–8)

See `docs/SQUADPLANNER_MODULES_5_8.md` for the detailed build spec.

**Module 5 — Itinerary Subgraph** (`agent/subgraphs/itinerary.py`)
The inner loop: neighborhood clustering → LLM itinerary → flight alignment → route planning → feasibility → validation.

**Module 6 — Orchestrator Graph Assembly** (`agent/graph.py`)
Wire all nodes into the parent StateGraph. Parallel fan-out. HITL interrupt. MongoDBCheckpointer.

**Module 7 — API Layer + SSE Streaming**
`api/trips.py`, `api/hitl.py`, `api/admin.py`, `utils/streaming.py`

**Module 8 — LangSmith + Integration Testing**
`tests/test_integration.py`, LangSmith tracing, pre-handoff checklist.

---

## Key Constraints — Never Violate These

- All DB operations use Motor (async). Never use pymongo directly anywhere.
- All LangGraph nodes must be `async def node_name(state) -> dict`
- `ItineraryState` must NOT import from `agent/graph.py` — no circular deps.
- SerpAPI calls MUST check budget gate BEFORE making the HTTP request.
- LLM is only called in 3 places: `select_destination`, `build_itinerary`, `assemble_output`.
  Everything else is deterministic Python.
- Timestamps: `datetime.now(timezone.utc).isoformat()` — not `utcnow()` (deprecated).
- `invite_code` is the public trip identifier. Never expose MongoDB `_id` in URLs.
- `trip_pitch` is overwritten on refinement. There is no versioning. This was a deliberate decision.
- Do not touch `/frontend`. It is owned by the frontend teammate.

---

## Folder Structure

```
backend/
├── main.py                    # FastAPI app, router registration, startup events
├── config.py                  # env vars, get_llm() factory, configure_langsmith()
├── requirements.txt
├── data/
│   └── destinations.json      # ~500 US destinations, static reference data
│
├── agent/
│   ├── graph.py               # Orchestrator StateGraph (Module 6)
│   ├── state.py               # TripState + ItineraryState TypedDicts (done)
│   ├── nodes/
│   │   ├── input_parser.py
│   │   ├── destination_selector.py
│   │   ├── tool_selector.py
│   │   ├── budget_analyzer.py
│   │   ├── hotel_searcher.py
│   │   ├── fairness_scorer.py
│   │   └── output_assembler.py
│   └── subgraphs/
│       └── itinerary.py       # Itinerary agent subgraph (Module 5)
│
├── tools/
│   ├── serpapi.py
│   ├── google_places.py
│   ├── google_routes.py
│   └── open_meteo.py
│
├── db/
│   ├── client.py
│   ├── checkpointer.py
│   └── models.py
│
├── api/
│   ├── trips.py               # POST /trips, GET /trips/{id}/stream
│   ├── hitl.py                # POST /trips/{id}/confirm-city
│   └── admin.py               # GET /admin/serpapi-usage
│
├── utils/
│   ├── preference_vectors.py
│   ├── neighborhood_cluster.py
│   └── streaming.py           # SSE formatting, NODE_PROGRESS_MAP
│
├── tests/
│   └── test_integration.py    # Module 8
│
└── docs/
    └── SQUADPLANNER_MODULES_5_8.md
```

---

## Environment Variables

```
MONGODB_URI=mongodb+srv://...
ANTHROPIC_API_KEY=sk-ant-...
SERPAPI_KEY=...
GOOGLE_PLACES_API_KEY=...
GOOGLE_ROUTES_API_KEY=...   # same key as Places if restricted to both
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=squadplanner
SERPAPI_MONTHLY_HARD_LIMIT=200
LLM_PROVIDER=anthropic       # switch to "groq" for free public hosting
```

---

## API Surface (What Frontend Calls)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/trips` | Create trip, get trip_id back |
| GET | `/trips/{id}/stream` | SSE stream of agent progress |
| POST | `/trips/{id}/confirm-city` | Resume graph after HITL city selection |
| GET | `/admin/serpapi-usage` | Check SerpAPI call count this month |
| GET | `/health` | Liveness check |

### SSE Event Types (what frontend receives)
- `NODE_PROGRESS` — agent moved to a new node, with human-readable message
- `HITL_REQUIRED` — agent paused, contains top 5 candidate destinations for UI
- `TRIP_COMPLETE` — agent finished, contains `trip_pitch` and `decision_log`

---

## After Module 8 — What Comes Next

These are planned but not started. Discuss and prioritize with the team.

### Short term (before launch)
- Google OAuth integration (users collection is designed, auth flow not built)
- Shareable invite link flow (backend stores invite_code, frontend handles join)
- Preference submission form (frontend, but backend needs a `PUT /trips/{id}/members/{member_id}/preferences` endpoint)
- Trip status polling endpoint (`GET /trips/{id}/status`) for frontend dashboard
- Refinement endpoint (`POST /trips/{id}/refine` with a natural language request)

### Medium term
- MCP server integration — this was a deferred learning goal. Once V1 is running,
  explore wrapping SerpAPI and Google Places as MCP servers and calling them
  from the agent using the MCP client pattern.
- Destination expansion — the 500-destination JSON can grow. Current batches:
  major cities, small towns, national parks, beach towns, mountain towns.
  Could add international destinations as a V2 scope item.
- Trip comparison — show two candidate cities side by side before HITL selection.

### Long term / V2
- International destinations (requires different flight search strategy)
- Real-time collaboration (multiple members editing refinements simultaneously)
- Booking integration (affiliate links to flights/hotels, not actual booking)
- Mobile app

---

## Portfolio / Interview Framing

Use this framing consistently when talking about the project:

**What it is:** "A multi-agent trip planning system built on LangGraph with a
Human-in-the-Loop workflow, parallel tool execution, and real-time SSE streaming."

**What makes it interesting:**
1. **StateGraph with conditional routing** — not a ReAct loop, not a chatbot.
   4 feedback loops, each with retry limits and deterministic routing logic.
2. **HITL with persistent state** — the agent pauses mid-execution, saves state
   to MongoDB via MongoDBCheckpointer, and resumes when the user confirms a city.
   Production pattern, not a demo trick.
3. **Dynamic tool selection** — the agent reads the group preference vector and
   decides which API calls to make. An adventure group skips the nightlife query entirely.
4. **Parallel fan-out** — flights for all members + activities + weather run concurrently
   via asyncio.gather, then join before budget analysis.
5. **Deterministic + LLM hybrid** — only 3 LLM calls in the entire pipeline.
   Everything else is deterministic Python. Intentional design for reliability and cost.

**What you'd do differently at scale:**
- Replace the 500-destination JSON with a vector database for semantic search
- Use a message queue (SQS or Redis) instead of background tasks for the graph execution
- Add proper auth (JWT) instead of session-based
- Separate the itinerary subgraph into its own microservice with its own deployment

---

## How to Work With This Codebase in Codex

### Starting a new session
Codex reads this file automatically via Cursor Rules. You do not need to re-explain
the project. Start with the specific task.

### Good prompts
- "Implement the `cluster_by_neighborhood` node in the itinerary subgraph per the spec in docs/SQUADPLANNER_MODULES_5_8.md"
- "The integration test is failing at the HITL resume step with this error: [paste error]. Fix it without changing the graph wiring."
- "Add a `PUT /trips/{id}/members/{member_id}/preferences` endpoint to api/trips.py"
- "The LLM call in build_itinerary is returning malformed JSON. Add better error handling and a fallback."

### Bad prompts (too vague)
- "Build the itinerary" — which part? Which file?
- "Fix the agent" — what's broken?
- "Make it better" — better how?

### When something breaks
Always provide: the exact error message, the file it came from, and what you were trying to do.
Do not ask Codex to "fix it" without the error — it will guess and make it worse.

### Brainstorming architecture
For any new feature, describe: the user action, what data is needed, which existing
system it touches. Codex will propose an approach consistent with the existing patterns.
Always validate against the constraints in this document before implementing.
