# SquadPlanner Testing Playbook

This file reconstructs the lost test context from the project bible, modules 5-8 spec,
the previous Codex session log, and the current backend tests.

## What We Are Proving

The backend is not just a CRUD API. The important proof is the full agent workflow:

1. `POST /trips` persists an initial trip state.
2. `GET /trips/{id}/stream` starts the LangGraph orchestrator and emits SSE progress.
3. The graph parses input, extracts natural-language constraints, scores destinations,
   and pauses at `city_selection_hitl`.
4. `POST /trips/{id}/confirm-city` resumes the graph with the selected destination.
5. The graph dynamically selects tools, fetches flights/activities/weather, checks
   budget, searches hotels, builds and validates the itinerary, checks fairness, and
   assembles the final pitch.
6. The stream returns `TRIP_COMPLETE` with itinerary JSON, constraint satisfaction,
   hotel, flights, fairness fields, and decision log.

## Demo Input Cases

Copy-pasteable payloads for the backend `/debug` UI live in:

`backend/tests/demo_input_cases.json`

Use these when manually testing the demo page. Each case has a `payload` object that
can be pasted directly into the Trip Input textarea.

The cases cover:

- `01_basic_smoke_completed` - basic happy path
- `02_preference_weight_conflict` - conflicting slider/weight preferences
- `03_natural_language_conflict` - conflicting notes and hard constraints
- `04_budget_limit_crossing` - tight budget and retry pressure
- `05_food_and_schedule_constraints` - dietary and late-start constraints
- `06_travel_origin_spread` - flight/fairness/alignment pressure
- `07_long_six_member_high_conflict_trip` - long six-member stress test
- `08_big_city_skyscraper_intent` - popular major-city regression for skyline/skyscraper requests

## Reconstructed Testcases

The structured payloads live in `backend/tests/manual_cases.json`.

### 1. Happy Path Relaxed Mixed Group

Use `happy_path_relaxed_mixed_group`.

This is the main demo case. It includes:

- Three travelers from `ORD`, `ATL`, and `LAX`
- A vegetarian member
- Natural-language constraints: no clubs, late mornings, relaxed pace, Italian meal
- Mixed preferences for outdoor, food, urban, shopping, and limited nightlife

Expected result:

- HITL shows 5 candidate destinations
- Confirming one city resumes the graph
- Final output has a non-empty pitch, hotel, flights, days, fairness result, decision log
- Each day includes `rationale` and `constraint_notes` explaining why the plan fits
- Constraint satisfaction mentions the no-club, Italian, relaxed pace, and late-morning rules

### 2. Budget Pressure Group

Use `budget_pressure_group`.

This case intentionally sets low budgets. It is meant to stress:

- `budget_analysis`
- destination retry behavior when `budget_status == "severe"`
- cheaper hotel retry behavior
- estimated flight/hotel fallbacks when live tools are constrained

Expected result:

- Budget status is set
- Severe status may route back to destination selection until retry limit
- Final output either fits the budget or explains the constrained budget outcome

### 3. Food Restriction Validation

Use `food_restriction_validation`.

This case combines `vegan`, `gluten_free`, and `halal` restrictions.

Expected result:

- Meals avoid meat, pork, bacon, ham, dairy, milk, egg, pasta, bread, flour, and wheat
- Day-level `constraint_notes` explain how the meal restrictions were handled
- `validation_gate` returns no food restriction errors
- If the LLM fails to honor a restriction, the deterministic validator reports it

### 4. Nightlife Hard Avoid

Use `nightlife_hard_avoid`.

This case gives a high nightlife vector score but also says no clubs/nightclubs.

Expected result:

- `dynamic_tool_selection` excludes nightlife
- fetched activities are filtered for club/nightlife terms
- day-level `rationale` explains quiet evening choices
- final itinerary contains no club activity

## Automated Tests

Run from `backend/`:

```powershell
python -m pytest tests/test_destination_selector.py tests/test_preference_constraints.py tests/test_graph_wiring.py -v
```

These tests are deterministic except graph initialization, which needs a valid
`MONGODB_URI` because the compiled graph uses the MongoDB checkpointer.

Live full-graph test:

```powershell
$env:RUN_LIVE_INTEGRATION = "true"
python -m pytest tests/test_integration.py -v -s
```

This spends live LLM and tool API quota. It writes run artifacts to
`backend/tests/artifacts/`.

To run a custom live payload from the reconstructed cases:

```powershell
$env:RUN_LIVE_INTEGRATION = "true"
$env:LIVE_TRIP_INPUT_JSON = '<paste one payload object from manual_cases.json>'
python -m pytest tests/test_integration.py -v -s
```

## Manual API Test

Start the backend:

```powershell
cd c:\Users\Patron\Documents\GitHub\squadplanner-ai\backend
python -m uvicorn main:app --reload
```

Open the debug UI:

```text
http://127.0.0.1:8000/debug
```

Or use the API directly:

```powershell
$payload = Get-Content .\tests\manual_cases.json -Raw | ConvertFrom-Json
$case = $payload.api_cases | Where-Object id -eq "happy_path_relaxed_mixed_group"
$trip = Invoke-RestMethod http://127.0.0.1:8000/trips -Method Post -ContentType "application/json" -Body ($case.payload | ConvertTo-Json -Depth 20)
$trip
```

Then stream:

```powershell
curl.exe -N "http://127.0.0.1:8000$($trip.stream_url)"
```

When the stream emits `HITL_REQUIRED`, choose one candidate and confirm:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/trips/$($trip.trip_id)/confirm-city" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"selected_destination":"New Orleans, LA","selected_destination_coords":{"lat":29.951,"lng":-90.071}}'
```

## Recovery Notes From The Lost Chat

The recovered session log shows that the previous build work included:

- experiments around LangGraph interrupt and `Command(resume=...)`
- graph wiring tests for Modules 6-8
- live-gated integration testing to avoid accidental API quota use
- preference-constraint work for no clubs, relaxed mornings, Italian meal, and activity filtering
- debug UI additions for trip input, candidate selection, progress, readable itinerary, JSON output, and constraint satisfaction

That context is now preserved here and in `backend/tests/manual_cases.json`.
