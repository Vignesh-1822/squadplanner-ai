# SquadPlanner — Codex Build Spec: Modules 5–8

## How to use this document
Work through each module in order. For each module:
1. Read the full module spec before writing any code
2. Build all files specified
3. Run the exact test commands listed at the end of the module
4. Do not start the next module until all tests pass

---

## Project State (What's Already Built)

The following are complete and working — do not modify them:

- `config.py` — settings, `get_llm()` factory (Claude Haiku 4.5 via Anthropic SDK)
- `main.py` — FastAPI app skeleton, `/health` endpoint
- `db/client.py` — Motor async MongoDB client singleton
- `db/checkpointer.py` — MongoDBCheckpointer scaffold
- `db/models.py` — Pydantic models
- `agent/state.py` — `TripState` and `ItineraryState` TypedDicts (complete)
- `tools/serpapi.py` — Flight + hotel search with budget gate (working)
- `tools/google_places.py` — Activity fetch by category (working)
- `tools/google_routes.py` — Route planning between activities (working)
- `tools/open_meteo.py` — Weather fetch (working)
- `agent/nodes/input_parser.py` — `parse_input` node (working)
- `agent/nodes/destination_selector.py` — `select_destination` node (working)
- `agent/nodes/tool_selector.py` — `dynamic_tool_selection` node (working)
- `agent/nodes/budget_analyzer.py` — `budget_analysis` node (working)
- `agent/nodes/hotel_searcher.py` — `search_hotel` node (working)
- `agent/nodes/fairness_scorer.py` — `compute_fairness` node (working)
- `agent/nodes/output_assembler.py` — `assemble_output` node (working)

## Key conventions already established
- All DB ops use Motor (async). Never use pymongo directly.
- All LangGraph nodes are `async def node_name(state) -> dict`
- Timestamps: `datetime.now(timezone.utc).isoformat()` (not utcnow)
- `DecisionLogEntry` is appended in every node's return dict
- `ItineraryState` must never import from `agent/graph.py`
- LLM is accessed via `get_llm()` from `config.py`
- State types imported from `agent.state`
- Tool functions imported from `tools/`

## Repo structure relevant to remaining modules
```
backend/
├── agent/
│   ├── graph.py               ← Module 6 builds this
│   ├── state.py               ← Already done
│   ├── nodes/                 ← Already done
│   └── subgraphs/
│       ├── __init__.py        ← Already exists (empty)
│       └── itinerary.py       ← Module 5 builds this
├── api/
│   ├── trips.py               ← Module 7 builds this
│   ├── hitl.py                ← Module 7 builds this
│   └── admin.py               ← Module 7 builds this
├── utils/
│   └── streaming.py           ← Module 7 builds this
└── tests/
    └── test_integration.py    ← Module 8 builds this
```

---

## Module 5 — Itinerary Agent Subgraph

### What this is
A standalone `StateGraph` that handles the full inner-loop itinerary planning.
It is called as a node inside the orchestrator (Module 6).
It uses `ItineraryState` from `agent/state.py`, NOT `TripState`.
It must NOT import from `agent/graph.py` — no circular dependencies.

Build this entirely in `agent/subgraphs/itinerary.py`.

### Helper: Haversine distance
Add this as a module-level function:
```python
import math

def haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng/2)**2
    return R * 2 * math.asin(math.sqrt(a))
```

### Node 1: `cluster_by_neighborhood`
```python
async def cluster_by_neighborhood(state: ItineraryState) -> dict:
```
- Groups `state["activities"]` into geographic clusters using greedy proximity (~1.5km radius)
- Algorithm:
  1. Copy activities into an unassigned list
  2. Take the first unassigned activity as a new cluster center
  3. Assign any unassigned activity within 1.5km (haversine) to that cluster
  4. Repeat until all assigned
- Assign clusters to days: spread evenly across `state["trip_duration_days"]`
  - If more clusters than days, merge smallest clusters
  - If fewer clusters than days, duplicate the largest cluster for extra days
- Each cluster dict: `{"day": int, "neighborhood": str, "center_lat": float, "center_lng": float, "activities": list[ActivityResult]}`
  - `neighborhood`: use the name of the center activity's address (first part before comma), or "Central [destination]" as fallback
- Store in `clustered_activities`
- Append `DecisionLogEntry`

### Node 2: `build_itinerary`
```python
async def build_itinerary(state: ItineraryState) -> dict:
```
- Increment `validation_rebuild_count` if `state["days"]` is not empty (this is a retry)
- Build a human-readable prompt summary from `state["clustered_activities"]`:
  - For each day cluster: day number, neighborhood name, list of activity names and categories
- Call `get_llm()` with a prompt that includes:
  - Destination name, trip dates, trip duration in days
  - The day-by-day activity clusters summary
  - Hotel name and address
  - Weather summary
  - All member food restrictions combined (deduplicated)
  - Group preference vector
  - Instruction: "Return ONLY a JSON array of DayPlan objects, no markdown, no backticks.
    Each DayPlan: {day_number: int, date: str (ISO), neighborhood: str,
    activities: [list of activity names as strings],
    meals: [exactly 3 strings: breakfast, lunch, dinner],
    estimated_day_cost_usd: float}"
  - Rules for the LLM:
    - Each day gets 3–5 activities from the cluster
    - Breakfast is always at or near the hotel
    - Lunch and dinner reference real neighborhood options
    - No food restriction violations in any meal
    - estimated_day_cost_usd = realistic estimate per person × number of members
- Parse the JSON response:
  - Strip markdown fences before parsing
  - On parse failure: log the error, return `state["days"]` unchanged (don't wipe existing days)
- Convert parsed dicts into `DayPlan` TypedDicts:
  - Activities field: keep as list of strings (activity names) for now — routes will be added by `plan_routes`
  - Routes: empty list `[]`
- Return: `{"days": list[DayPlan], "validation_rebuild_count": updated_count}`
- Append `DecisionLogEntry`

### Node 3: `align_flight_times`
```python
async def align_flight_times(state: ItineraryState) -> dict:
```
- Find latest departure across all members:
  - Parse `flight["depart_time"]` for each flight in `state["flights"]`
  - Latest depart_time = Day 1 arrival. Add 1.5 hours buffer.
  - If `state["days"]` has a Day 1, trim its activities to remove any before arrival + buffer
  - In practice: if arrival is after noon, cap Day 1 at 3 activities max
- Find earliest return across all members:
  - Parse `flight["return_time"]` for each flight in `state["flights"]`
  - Earliest return = last day cutoff. Subtract 2.5 hours for airport transit.
  - If last day activities would run past this, trim to 2 activities max
- If `state["flights"]` is empty, skip alignment (no-op)
- Return: `{"days": updated_days}`
- Append `DecisionLogEntry`

### Node 4: `plan_routes`
```python
async def plan_routes(state: ItineraryState) -> dict:
```
- For each day in `state["days"]`:
  - Extract activities as `ActivityResult` objects:
    - Match activity names in the day against `state["activities"]` list by name
    - For any activity name not found, skip routing for that activity
  - If 2+ activities found, call `tools.google_routes.plan_day_routes(matched_activities)`
  - Store result: update `day["routes"]` with route list, and add `day["total_travel_minutes"]` key
  - If < 2 activities: set `day["routes"] = []`, `day["total_travel_minutes"] = 0`
- Return: `{"days": updated_days}`
- Append `DecisionLogEntry`

### Conditional function: `check_feasibility`
```python
def check_feasibility(state: ItineraryState) -> str:
```
- This is a routing function, not a node — no `async`, no state update
- For each day with `total_travel_minutes` > 180 (3 hours):
  - If `state["feasibility_swap_count"] < 2`:
    - Remove the last activity from that day (simplest swap)
    - Increment `feasibility_swap_count` in state directly (mutate — this is a router)
    - Return `"swap"` → graph routes back to `plan_routes`
  - Else: accept and continue
- If all days have `total_travel_minutes <= 180` OR swap count exhausted: return `"pass"`

### Node 5: `validation_gate`
```python
async def validation_gate(state: ItineraryState) -> dict:
```
Deterministic checks — collect all failures into `validation_errors`:
1. Each day has exactly 3 meals
2. No day has 0 activities
3. No meal string contains any food restriction keyword from any member
   - Build restriction keywords from `state["members"][*]["food_restrictions"]`
   - e.g. if "vegetarian" is a restriction, flag any meal containing "beef", "chicken", "pork", "meat"
   - Keyword map: `{"vegetarian": ["beef","chicken","pork","meat","bacon","steak"], "vegan": ["beef","chicken","pork","meat","bacon","steak","cheese","dairy","milk","egg"], "halal": ["pork","bacon","ham","lard"], "gluten_free": ["pasta","bread","flour","wheat"]}`
4. Total estimated cost across all days + hotel total + average flight cost per person <= group total budget
   - avg_flight_cost = sum(f["price_usd"] for f in state["flights"]) / max(len(state["members"]), 1)
   - total_cost = sum(day["estimated_day_cost_usd"] for day in days) + state["hotel"]["total_price_usd"] + avg_flight_cost * len(members)
   - group_budget = sum(m["budget_usd"] for m in state["members"])
   - Fail if total_cost > group_budget * 1.15 (allow 15% buffer)
5. Correct number of days: len(days) == state["trip_duration_days"]

Return: `{"validation_errors": list[str]}`
Append `DecisionLogEntry` with errors summary

### Conditional function: `check_validation`
```python
def check_validation(state: ItineraryState) -> str:
```
- If `state["validation_errors"]` is empty: return `"pass"`
- If `state["validation_rebuild_count"] < 2`: return `"rebuild"`
- Else: return `"pass"` (accept with errors — don't loop forever)

### Graph wiring
```python
from langgraph.graph import StateGraph, END

graph = StateGraph(ItineraryState)

graph.add_node("cluster_by_neighborhood", cluster_by_neighborhood)
graph.add_node("build_itinerary", build_itinerary)
graph.add_node("align_flight_times", align_flight_times)
graph.add_node("plan_routes", plan_routes)
graph.add_node("validation_gate", validation_gate)

graph.set_entry_point("cluster_by_neighborhood")
graph.add_edge("cluster_by_neighborhood", "build_itinerary")
graph.add_edge("build_itinerary", "align_flight_times")
graph.add_edge("align_flight_times", "plan_routes")
graph.add_conditional_edges(
    "plan_routes",
    check_feasibility,
    {"swap": "plan_routes", "pass": "validation_gate"}
)
graph.add_conditional_edges(
    "validation_gate",
    check_validation,
    {"rebuild": "build_itinerary", "pass": END}
)

itinerary_graph = graph.compile()
```

### Helper function (add at bottom of file)
```python
async def run_itinerary_subgraph(trip_state: dict) -> dict:
    """
    Maps TripState fields into ItineraryState, invokes the subgraph, returns final ItineraryState.
    Called by the orchestrator as a regular async function — not as a LangGraph node invocation.
    """
    itinerary_input: ItineraryState = {
        "trip_id": trip_state["trip_id"],
        "destination": trip_state["selected_destination"],
        "destination_coords": trip_state["selected_destination_coords"] or {"lat": 0.0, "lng": 0.0},
        "start_date": trip_state["start_date"],
        "end_date": trip_state["end_date"],
        "trip_duration_days": trip_state["trip_duration_days"],
        "members": trip_state["members"],
        "activities": trip_state["activities"],
        "hotel": trip_state["hotel"],
        "flights": trip_state["flights"],
        "weather": trip_state.get("weather"),
        "clustered_activities": [],
        "days": [],
        "feasibility_swap_count": 0,
        "validation_rebuild_count": 0,
        "validation_errors": [],
        "decision_log": [],
        "error": None,
    }
    result = await itinerary_graph.ainvoke(itinerary_input)
    return result
```

### Module 5 test
Add this `__main__` block and run it:
```python
if __name__ == "__main__":
    import asyncio
    from datetime import date, timedelta

    # Mock activities spread across two geographic clusters
    mock_activities = [
        {"place_id": "p1", "name": "City Park", "category": "outdoor",
         "address": "French Quarter, New Orleans, LA", "lat": 29.960, "lng": -90.060,
         "price_level": 0, "rating": 4.5, "tags": ["park", "outdoor"]},
        {"place_id": "p2", "name": "Jazz Museum", "category": "culture",
         "address": "French Quarter, New Orleans, LA", "lat": 29.961, "lng": -90.061,
         "price_level": 1, "rating": 4.7, "tags": ["museum", "historic"]},
        {"place_id": "p3", "name": "Cafe Du Monde", "category": "food",
         "address": "French Quarter, New Orleans, LA", "lat": 29.958, "lng": -90.062,
         "price_level": 1, "rating": 4.6, "tags": ["restaurant", "cafe"]},
        {"place_id": "p4", "name": "Audubon Park", "category": "outdoor",
         "address": "Garden District, New Orleans, LA", "lat": 29.924, "lng": -90.131,
         "price_level": 0, "rating": 4.4, "tags": ["park", "nature"]},
        {"place_id": "p5", "name": "Garden District Walk", "category": "culture",
         "address": "Garden District, New Orleans, LA", "lat": 29.926, "lng": -90.130,
         "price_level": 0, "rating": 4.3, "tags": ["historic", "walking"]},
    ]

    mock_state = {
        "trip_id": "test-001",
        "destination": "New Orleans, LA",
        "destination_coords": {"lat": 29.951, "lng": -90.071},
        "start_date": "2026-06-01",
        "end_date": "2026-06-03",
        "trip_duration_days": 2,
        "members": [
            {"member_id": "alice", "name": "Alice", "origin_city": "ORD",
             "budget_usd": 1200.0, "food_restrictions": ["vegetarian"],
             "preference_vector": {"outdoor": 0.8, "food": 0.7, "nightlife": 0.2, "culture": 0.6, "shopping": 0.1},
             "is_leader": True},
            {"member_id": "bob", "name": "Bob", "origin_city": "ATL",
             "budget_usd": 1000.0, "food_restrictions": [],
             "preference_vector": {"outdoor": 0.6, "food": 0.8, "nightlife": 0.5, "culture": 0.4, "shopping": 0.3},
             "is_leader": False},
        ],
        "activities": mock_activities,
        "hotel": {"name": "Hotel Monteleone", "address": "214 Royal St, New Orleans",
                  "price_per_night_usd": 180.0, "total_price_usd": 360.0,
                  "rating": 4.5, "is_estimated": False},
        "flights": [
            {"member_id": "alice", "origin": "ORD", "destination": "MSY",
             "price_usd": 280.0, "airline": "Southwest", "depart_time": "2026-06-01T10:00:00",
             "return_time": "2026-06-03T17:00:00", "is_estimated": False},
            {"member_id": "bob", "origin": "ATL", "destination": "MSY",
             "price_usd": 210.0, "airline": "Delta", "depart_time": "2026-06-01T11:30:00",
             "return_time": "2026-06-03T18:00:00", "is_estimated": False},
        ],
        "weather": {"destination": "New Orleans", "date_range": "2026-06-01 to 2026-06-03",
                    "avg_temp_c": 28.0, "precipitation_mm": 5.0, "summary": "Warm (28°C avg), mostly dry"},
        "clustered_activities": [],
        "days": [],
        "feasibility_swap_count": 0,
        "validation_rebuild_count": 0,
        "validation_errors": [],
        "decision_log": [],
        "error": None,
    }

    async def test():
        result = await itinerary_graph.ainvoke(mock_state)
        print(f"\n=== ITINERARY SUBGRAPH RESULT ===")
        print(f"Days built: {len(result['days'])}")
        print(f"Validation errors: {result['validation_errors']}")
        print(f"Decision log entries: {len(result['decision_log'])}")
        for day in result["days"]:
            print(f"\nDay {day['day_number']} — {day['neighborhood']}")
            print(f"  Activities: {day['activities']}")
            print(f"  Meals: {day['meals']}")
            print(f"  Estimated cost: ${day['estimated_day_cost_usd']}")

    asyncio.run(test())
```

**Expected output:**
- `Days built: 2`
- `Validation errors: []` (or minor errors if LLM doesn't perfectly follow format)
- Each day has a neighborhood, 3 meals, activities list, and cost estimate
- Decision log has at least 4 entries (one per node)

---

## Module 6 — Orchestrator Graph Assembly

### What this is
The parent `StateGraph` that wires all orchestrator nodes together with conditional edges,
handles HITL (Human-in-the-Loop) city selection, parallel data fetching, and invokes the
itinerary subgraph. Build this in `agent/graph.py`.

### Imports
```python
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from agent.state import TripState
from agent.nodes.input_parser import parse_input
from agent.nodes.destination_selector import select_destination
from agent.nodes.tool_selector import dynamic_tool_selection
from agent.nodes.budget_analyzer import budget_analysis
from agent.nodes.hotel_searcher import search_hotel
from agent.nodes.fairness_scorer import compute_fairness
from agent.nodes.output_assembler import assemble_output
from agent.subgraphs.itinerary import run_itinerary_subgraph
from tools.serpapi import search_flights
from tools.google_places import fetch_activities_by_category
from tools.open_meteo import fetch_weather
from db.checkpointer import get_checkpointer
```

### Parallel fan-out node
```python
async def parallel_data_fetch(state: TripState) -> dict:
    import asyncio
    from datetime import datetime, timezone

    # Run all three fetch operations concurrently
    flight_tasks = [
        search_flights(
            origin=member["origin_city"],
            destination=state["selected_destination"],
            depart_date=state["start_date"],
            return_date=state["end_date"],
            adults=1
        )
        for member in state["members"]
    ]

    places_task = fetch_activities_by_category(
        destination=state["selected_destination"],
        coords=state["selected_destination_coords"],
        categories=state["active_tool_categories"],
    )

    weather_task = fetch_weather(
        lat=state["selected_destination_coords"]["lat"],
        lng=state["selected_destination_coords"]["lng"],
        start_date=state["start_date"],
        end_date=state["end_date"],
        destination_name=state["selected_destination"],
    )

    # Gather all concurrently
    results = await asyncio.gather(
        *flight_tasks,
        places_task,
        weather_task,
        return_exceptions=True
    )

    # Split results
    n_members = len(state["members"])
    flight_results = []
    for i, member in enumerate(state["members"]):
        r = results[i]
        if isinstance(r, Exception):
            # Fallback estimated flight
            flight_results.append({
                "member_id": member["member_id"],
                "origin": member["origin_city"],
                "destination": state["selected_destination"],
                "price_usd": 300.0, "airline": "Estimated",
                "depart_time": state["start_date"] + "T12:00:00",
                "return_time": state["end_date"] + "T12:00:00",
                "is_estimated": True
            })
        else:
            r["member_id"] = member["member_id"]
            flight_results.append(r)

    activities_result = results[n_members]
    weather_result = results[n_members + 1]

    activities = activities_result if not isinstance(activities_result, Exception) else []
    weather = weather_result if not isinstance(weather_result, Exception) else None

    return {
        "flights": flight_results,
        "activities": activities,
        "weather": weather,
        "decision_log": [{
            "node": "parallel_data_fetch",
            "decision": f"Fetched {len(flight_results)} flights, {len(activities)} activities",
            "reason": f"Weather: {weather['summary'] if weather else 'unavailable'}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }
```

### HITL node
```python
async def city_selection_hitl(state: TripState) -> dict:
    """
    Pauses the graph and waits for the trip leader to confirm a destination.
    The orchestrator calls interrupt() here — LangGraph saves state and suspends.
    When the API resumes the graph (POST /trips/{id}/confirm-city), the resume
    value contains the selected destination.
    """
    resume_value = interrupt({
        "type": "city_selection",
        "candidate_destinations": state["candidate_destinations"]
    })
    # resume_value is set by the HITL API endpoint when it resumes the graph
    return {
        "selected_destination": resume_value.get("selected_destination"),
        "selected_destination_coords": resume_value.get("selected_destination_coords"),
    }
```

### Itinerary subgraph node
```python
async def run_itinerary_node(state: TripState) -> dict:
    """Calls the itinerary subgraph and merges results back into TripState."""
    from datetime import datetime, timezone
    result = await run_itinerary_subgraph(state)
    return {
        "days": result.get("days", []),
        "decision_log": result.get("decision_log", []) + [{
            "node": "run_itinerary_node",
            "decision": f"Itinerary complete: {len(result.get('days', []))} days",
            "reason": f"Validation errors: {result.get('validation_errors', [])}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }
```

### Routing functions (conditional edges)
```python
def route_after_budget(state: TripState) -> str:
    status = state.get("budget_status", "ok")
    if status == "severe":
        # Check retry limit
        if state.get("destination_retry_count", 0) >= 3:
            return "ok"  # Give up retrying, continue with current destination
        return "severe"
    elif status == "moderate":
        return "moderate"
    return "ok"

def route_after_fairness(state: TripState) -> str:
    if not state.get("fairness_passed", True) and state.get("hotel_retry_count", 0) < 1:
        return "retry_hotel"
    return "done"
```

### Graph wiring
```python
def build_graph():
    graph = StateGraph(TripState)

    # Register all nodes
    graph.add_node("parse_input", parse_input)
    graph.add_node("select_destination", select_destination)
    graph.add_node("city_selection_hitl", city_selection_hitl)
    graph.add_node("dynamic_tool_selection", dynamic_tool_selection)
    graph.add_node("parallel_data_fetch", parallel_data_fetch)
    graph.add_node("budget_analysis", budget_analysis)
    graph.add_node("search_hotel", search_hotel)
    graph.add_node("run_itinerary_node", run_itinerary_node)
    graph.add_node("compute_fairness", compute_fairness)
    graph.add_node("assemble_output", assemble_output)

    # Linear edges
    graph.set_entry_point("parse_input")
    graph.add_edge("parse_input", "select_destination")
    graph.add_edge("select_destination", "city_selection_hitl")
    graph.add_edge("city_selection_hitl", "dynamic_tool_selection")
    graph.add_edge("dynamic_tool_selection", "parallel_data_fetch")
    graph.add_edge("parallel_data_fetch", "budget_analysis")

    # Budget routing
    graph.add_conditional_edges(
        "budget_analysis",
        route_after_budget,
        {
            "severe": "select_destination",   # retry with next city
            "moderate": "search_hotel",        # lower ceiling and search hotel
            "ok": "search_hotel"               # proceed normally
        }
    )

    # After hotel
    graph.add_edge("search_hotel", "run_itinerary_node")
    graph.add_edge("run_itinerary_node", "compute_fairness")

    # Fairness routing
    graph.add_conditional_edges(
        "compute_fairness",
        route_after_fairness,
        {
            "retry_hotel": "search_hotel",
            "done": "assemble_output"
        }
    )

    graph.add_edge("assemble_output", END)

    return graph
```

### Checkpointer and compilation
```python
async def get_compiled_graph():
    """Returns the compiled graph with MongoDB checkpointer for HITL support."""
    checkpointer = await get_checkpointer()
    graph = build_graph()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["city_selection_hitl"]
    )

# Module-level compiled graph (initialized at startup)
orchestrator_graph = None

async def initialize_graph():
    global orchestrator_graph
    orchestrator_graph = await get_compiled_graph()
```

Call `initialize_graph()` from `main.py`'s startup event.

### Update `db/checkpointer.py`
The checkpointer needs to use the Motor client and return an async context:
```python
from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver
from db.client import get_database

async def get_checkpointer():
    db = get_database()
    return AsyncMongoDBSaver(db.client, db.name)
```

Note: `AsyncMongoDBSaver` is from `langgraph-checkpoint-mongodb`. Add to `requirements.txt` if not already there:
```
langgraph-checkpoint-mongodb
```

### Module 6 test
```python
# Run from backend/ directory:
# python -m pytest tests/test_graph_wiring.py -v

# Create tests/test_graph_wiring.py:
import pytest
import asyncio
from agent.graph import build_graph, initialize_graph
from agent.state import TripState

def test_graph_builds():
    """Confirm the graph compiles without errors."""
    graph = build_graph()
    compiled = graph.compile()
    assert compiled is not None

def test_graph_nodes():
    """Confirm all expected nodes are registered."""
    graph = build_graph()
    expected_nodes = {
        "parse_input", "select_destination", "city_selection_hitl",
        "dynamic_tool_selection", "parallel_data_fetch", "budget_analysis",
        "search_hotel", "run_itinerary_node", "compute_fairness", "assemble_output"
    }
    assert expected_nodes.issubset(set(graph.nodes.keys()))

@pytest.mark.asyncio
async def test_graph_initializes():
    """Confirm graph compiles with checkpointer."""
    await initialize_graph()
    from agent.graph import orchestrator_graph
    assert orchestrator_graph is not None
```

**Expected output:**
```
tests/test_graph_wiring.py::test_graph_builds PASSED
tests/test_graph_wiring.py::test_graph_nodes PASSED
tests/test_graph_wiring.py::test_graph_initializes PASSED
```

---

## Module 7 — API Layer + SSE Streaming

### What this is
Three FastAPI routers and the SSE streaming utility. After this module, you can
`curl` the streaming endpoint and watch node progress in real time in your terminal.

### `utils/streaming.py`

```python
import json
from typing import AsyncGenerator
from datetime import datetime, timezone

NODE_PROGRESS_MAP = {
    "parse_input":             "Validating trip details...",
    "select_destination":      "Scoring destinations for your group...",
    "city_selection_hitl":     "Waiting for city selection...",
    "dynamic_tool_selection":  "Selecting data sources based on group preferences...",
    "parallel_data_fetch":     "Fetching flights, activities, and weather...",
    "budget_analysis":         "Analysing group budget...",
    "search_hotel":            "Finding hotels within budget...",
    "cluster_by_neighborhood": "Grouping activities by neighbourhood...",
    "build_itinerary":         "Building your itinerary...",
    "align_flight_times":      "Aligning schedule with flight times...",
    "plan_routes":             "Planning routes between activities...",
    "validation_gate":         "Validating itinerary...",
    "compute_fairness":        "Checking cost fairness across the group...",
    "assemble_output":         "Writing your trip pitch...",
}

def format_sse_event(event_type: str, data: dict) -> str:
    payload = json.dumps({"event_type": event_type, "data": data})
    return f"data: {payload}\n\n"

async def stream_graph_events(
    trip_id: str,
    initial_state: dict,
) -> AsyncGenerator[str, None]:
    from agent.graph import orchestrator_graph

    config = {"configurable": {"thread_id": trip_id}}

    async for event in orchestrator_graph.astream_events(
        initial_state, config=config, version="v2"
    ):
        kind = event.get("event")
        name = event.get("name", "")

        if kind == "on_chain_start" and name in NODE_PROGRESS_MAP:
            yield format_sse_event("NODE_PROGRESS", {
                "node": name,
                "message": NODE_PROGRESS_MAP[name],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        elif kind == "on_chain_start" and name == "city_selection_hitl":
            # Extract candidate destinations from state snapshot
            snapshot = await orchestrator_graph.aget_state(config)
            candidates = snapshot.values.get("candidate_destinations", [])
            yield format_sse_event("HITL_REQUIRED", {
                "trip_id": trip_id,
                "candidate_destinations": candidates
            })

        elif kind == "on_chain_end" and name == "assemble_output":
            output = event.get("data", {}).get("output", {})
            yield format_sse_event("TRIP_COMPLETE", {
                "trip_id": trip_id,
                "trip_pitch": output.get("trip_pitch", ""),
                "decision_log": output.get("decision_log", [])
            })
```

### `api/trips.py`

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime, timezone

from agent.state import MemberInput
from utils.streaming import stream_graph_events
from db.client import get_collection

router = APIRouter(prefix="/trips", tags=["trips"])

class MemberRequest(BaseModel):
    member_id: str
    name: str
    origin_city: str
    budget_usd: float
    food_restrictions: list[str] = []
    preference_vector: dict[str, float]
    is_leader: bool

class CreateTripRequest(BaseModel):
    members: list[MemberRequest]
    start_date: str
    end_date: str

@router.post("")
async def create_trip(request: CreateTripRequest, background_tasks: BackgroundTasks):
    trip_id = str(uuid.uuid4())

    # Build initial TripState
    initial_state = {
        "trip_id": trip_id,
        "members": [m.model_dump() for m in request.members],
        "start_date": request.start_date,
        "end_date": request.end_date,
        "trip_duration_days": 0,
        "preference_conflicts": [],
        "group_preference_vector": {},
        "active_tool_categories": [],
        "candidate_destinations": [],
        "selected_destination": None,
        "selected_destination_coords": None,
        "flights": [],
        "activities": [],
        "weather": None,
        "budget_status": None,
        "budget_ceiling_hotel_usd": None,
        "hotel": None,
        "days": [],
        "fairness_scores": {},
        "compatibility_scores": {},
        "fairness_passed": False,
        "trip_pitch": None,
        "decision_log": [],
        "destination_retry_count": 0,
        "hotel_retry_count": 0,
        "error": None,
    }

    # Save trip to MongoDB with pending status
    trips = get_collection("trips")
    await trips.insert_one({
        "_id": trip_id,
        "trip_id": trip_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "initial_state": initial_state,
    })

    return {"trip_id": trip_id, "status": "started", "stream_url": f"/trips/{trip_id}/stream"}

@router.get("/{trip_id}/stream")
async def stream_trip(trip_id: str):
    trips = get_collection("trips")
    trip = await trips.find_one({"trip_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    initial_state = trip["initial_state"]

    return StreamingResponse(
        stream_graph_events(trip_id, initial_state),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )
```

### `api/hitl.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agent.graph import orchestrator_graph
from db.client import get_collection

router = APIRouter(prefix="/trips", tags=["hitl"])

class CityConfirmRequest(BaseModel):
    selected_destination: str
    selected_destination_coords: dict  # {"lat": float, "lng": float}

@router.post("/{trip_id}/confirm-city")
async def confirm_city(trip_id: str, body: CityConfirmRequest):
    config = {"configurable": {"thread_id": trip_id}}

    # Check graph is actually interrupted at city selection
    snapshot = await orchestrator_graph.aget_state(config)
    if not snapshot or "city_selection_hitl" not in (snapshot.next or []):
        raise HTTPException(
            status_code=400,
            detail="Trip is not waiting for city selection"
        )

    # Resume the graph with the selected city
    await orchestrator_graph.aupdate_state(
        config,
        {
            "selected_destination": body.selected_destination,
            "selected_destination_coords": body.selected_destination_coords,
        },
        as_node="city_selection_hitl"
    )

    # Update trip status in MongoDB
    trips = get_collection("trips")
    await trips.update_one(
        {"trip_id": trip_id},
        {"$set": {"status": "generating", "selected_destination": body.selected_destination}}
    )

    return {"status": "resumed", "trip_id": trip_id, "destination": body.selected_destination}
```

### `api/admin.py`

```python
from fastapi import APIRouter
from datetime import datetime, timezone
from db.client import get_collection
from config import settings

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/serpapi-usage")
async def get_serpapi_usage():
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    cache = get_collection("api_cache")
    doc = await cache.find_one({"type": "serpapi_usage", "month": current_month})
    calls_used = doc["calls_used"] if doc else 0
    return {
        "month": current_month,
        "calls_used": calls_used,
        "hard_limit": settings.SERPAPI_MONTHLY_HARD_LIMIT,
        "remaining": settings.SERPAPI_MONTHLY_HARD_LIMIT - calls_used
    }
```

### Update `main.py`
Register all routers and initialize the graph on startup:
```python
from api import trips, hitl, admin
from agent.graph import initialize_graph

app.include_router(trips.router)
app.include_router(hitl.router)
app.include_router(admin.router)

@app.on_event("startup")
async def startup():
    # existing DB connection code...
    await initialize_graph()
```

### Module 7 test
Run the server and test each endpoint:

```bash
# Terminal 1 — start the server
cd backend
uvicorn main:app --reload

# Terminal 2 — run these curl commands one by one

# 1. Health check
curl http://localhost:8000/health
# Expected: {"status":"ok","db":"connected"}

# 2. Create a trip
curl -X POST http://localhost:8000/trips \
  -H "Content-Type: application/json" \
  -d '{
    "members": [{
      "member_id": "alice",
      "name": "Alice",
      "origin_city": "ORD",
      "budget_usd": 1500,
      "food_restrictions": [],
      "preference_vector": {"outdoor":0.8,"food":0.7,"nightlife":0.2,"culture":0.6,"shopping":0.1},
      "is_leader": true
    }],
    "start_date": "2026-07-01",
    "end_date": "2026-07-04"
  }'
# Expected: {"trip_id":"<uuid>","status":"started","stream_url":"/trips/<uuid>/stream"}
# Save the trip_id from the response

# 3. Stream the trip (replace <trip_id> with value from step 2)
curl -N http://localhost:8000/trips/<trip_id>/stream
# Expected: SSE events streaming in terminal
# First event should be: data: {"event_type":"NODE_PROGRESS","data":{"node":"parse_input",...}}
# Graph will pause at city_selection_hitl and emit HITL_REQUIRED event

# 4. Confirm city (use a destination id from the HITL_REQUIRED event)
curl -X POST http://localhost:8000/trips/<trip_id>/confirm-city \
  -H "Content-Type: application/json" \
  -d '{"selected_destination":"New Orleans, LA","selected_destination_coords":{"lat":29.951,"lng":-90.071}}'
# Expected: {"status":"resumed","trip_id":"...","destination":"New Orleans, LA"}

# 5. Admin endpoint
curl http://localhost:8000/admin/serpapi-usage
# Expected: {"month":"2026-04","calls_used":N,"hard_limit":200,"remaining":200-N}
```

---

## Module 8 — LangSmith + Integration Testing

### What this is
Enable full observability via LangSmith, then run a complete end-to-end integration
test that exercises every node in the graph. This is your proof of life before
frontend integration.

### LangSmith setup in `config.py`
Ensure this block exists and is called before the graph is imported:
```python
import os

def configure_langsmith():
    if settings.LANGCHAIN_TRACING_V2.lower() == "true":
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
```

Call `configure_langsmith()` at the top of `main.py` startup — before any LangGraph import.

### LangSmith account setup
1. Go to smith.langchain.com and create a free account
2. Settings → API Keys → Create API Key
3. Add to `.env`:
   ```
   LANGCHAIN_API_KEY=ls__your_key_here
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_PROJECT=squadplanner
   ```

### `tests/test_integration.py`
Build a full integration test. This test simulates a real trip from POST to completion,
including the HITL interrupt.

```python
import pytest
import asyncio
from agent.graph import initialize_graph, orchestrator_graph

MOCK_INITIAL_STATE = {
    "trip_id": "integration-test-001",
    "members": [
        {
            "member_id": "alice",
            "name": "Alice",
            "origin_city": "ORD",
            "budget_usd": 1500.0,
            "food_restrictions": ["vegetarian"],
            "preference_vector": {"outdoor": 0.8, "food": 0.7, "nightlife": 0.2, "culture": 0.6, "shopping": 0.1},
            "is_leader": True,
        },
        {
            "member_id": "bob",
            "name": "Bob",
            "origin_city": "ATL",
            "budget_usd": 1200.0,
            "food_restrictions": [],
            "preference_vector": {"outdoor": 0.5, "food": 0.8, "nightlife": 0.6, "culture": 0.4, "shopping": 0.3},
            "is_leader": False,
        },
        {
            "member_id": "carol",
            "name": "Carol",
            "origin_city": "LAX",
            "budget_usd": 2000.0,
            "food_restrictions": [],
            "preference_vector": {"outdoor": 0.6, "food": 0.6, "nightlife": 0.4, "culture": 0.7, "shopping": 0.5},
            "is_leader": False,
        },
    ],
    "start_date": "2026-07-10",
    "end_date": "2026-07-13",
    "trip_duration_days": 0,
    "preference_conflicts": [],
    "group_preference_vector": {},
    "active_tool_categories": [],
    "candidate_destinations": [],
    "selected_destination": None,
    "selected_destination_coords": None,
    "flights": [],
    "activities": [],
    "weather": None,
    "budget_status": None,
    "budget_ceiling_hotel_usd": None,
    "hotel": None,
    "days": [],
    "fairness_scores": {},
    "compatibility_scores": {},
    "fairness_passed": False,
    "trip_pitch": None,
    "decision_log": [],
    "destination_retry_count": 0,
    "hotel_retry_count": 0,
    "error": None,
}

@pytest.mark.asyncio
async def test_full_trip_integration():
    await initialize_graph()

    config = {"configurable": {"thread_id": "integration-test-001"}}

    # Phase 1: Run until HITL interrupt
    print("\n=== Phase 1: Running to HITL interrupt ===")
    async for event in orchestrator_graph.astream_events(
        MOCK_INITIAL_STATE, config=config, version="v2"
    ):
        if event["event"] == "on_chain_start":
            print(f"  → Node: {event['name']}")
        if event["name"] == "city_selection_hitl":
            break

    # Check state at interrupt
    snapshot = await orchestrator_graph.aget_state(config)
    assert snapshot is not None, "Graph should have saved state at interrupt"
    candidates = snapshot.values.get("candidate_destinations", [])
    assert len(candidates) == 5, f"Expected 5 candidates, got {len(candidates)}"
    print(f"\nTop destination: {candidates[0]['name']} (score: {candidates[0]['score']:.3f})")
    print(f"LLM reasoning: {candidates[0]['llm_reasoning']}")

    # Phase 2: Confirm city and resume
    print("\n=== Phase 2: Confirming city and resuming ===")
    chosen = candidates[0]
    await orchestrator_graph.aupdate_state(
        config,
        {
            "selected_destination": chosen["name"],
            "selected_destination_coords": chosen["coords"],
        },
        as_node="city_selection_hitl"
    )

    # Phase 3: Run to completion
    print("\n=== Phase 3: Running to completion ===")
    final_state = None
    async for event in orchestrator_graph.astream_events(
        None, config=config, version="v2"
    ):
        if event["event"] == "on_chain_start" and event["name"] in [
            "dynamic_tool_selection", "parallel_data_fetch", "budget_analysis",
            "search_hotel", "run_itinerary_node", "compute_fairness", "assemble_output"
        ]:
            print(f"  → Node: {event['name']}")

    # Get final state
    final_snapshot = await orchestrator_graph.aget_state(config)
    final_state = final_snapshot.values

    # Assertions
    print("\n=== Assertions ===")

    assert final_state.get("trip_pitch"), "trip_pitch should be non-empty"
    print(f"✓ trip_pitch generated ({len(final_state['trip_pitch'])} chars)")

    assert len(final_state.get("days", [])) > 0, "days should have at least 1 entry"
    print(f"✓ days: {len(final_state['days'])} days built")

    assert len(final_state.get("decision_log", [])) >= 8, "Expected at least 8 decision log entries"
    print(f"✓ decision_log: {len(final_state['decision_log'])} entries")

    assert final_state.get("hotel") is not None, "hotel should be populated"
    print(f"✓ hotel: {final_state['hotel']['name']}")

    assert "fairness_passed" in final_state, "fairness_passed should be set"
    print(f"✓ fairness_passed: {final_state['fairness_passed']}")

    assert len(final_state.get("flights", [])) == 3, "Should have 3 flights (one per member)"
    print(f"✓ flights: {len(final_state['flights'])} found")

    print("\n=== Trip Pitch Preview ===")
    print(final_state["trip_pitch"][:500] + "...")

    print("\n=== Decision Log ===")
    for entry in final_state["decision_log"]:
        print(f"  [{entry['node']}] {entry['decision']}")
```

### Run the integration test
```bash
# Install pytest-asyncio if not already in requirements.txt
pip install pytest-asyncio

# Add to requirements.txt:
# pytest
# pytest-asyncio

# Run the test
cd backend
python -m pytest tests/test_integration.py -v -s
```

**Expected output:**
```
=== Phase 1: Running to HITL interrupt ===
  → Node: parse_input
  → Node: select_destination
  → Node: city_selection_hitl

Top destination: [City Name] (score: 0.XXX)
LLM reasoning: [Destination-specific reasoning]

=== Phase 2: Confirming city and resuming ===

=== Phase 3: Running to completion ===
  → Node: dynamic_tool_selection
  → Node: parallel_data_fetch
  → Node: budget_analysis
  → Node: search_hotel
  → Node: run_itinerary_node
  → Node: compute_fairness
  → Node: assemble_output

=== Assertions ===
✓ trip_pitch generated (XXX chars)
✓ days: 3 days built
✓ decision_log: XX entries
✓ hotel: [Hotel Name]
✓ fairness_passed: True/False
✓ flights: 3 found

PASSED
```

Also verify in LangSmith dashboard (smith.langchain.com):
- A trace named "squadplanner" should appear
- Every node is visible as a span with token counts and latency
- The full state at each step is inspectable

---

## Pre-handoff Checklist

Run through this before telling the frontend team the backend is ready:

```
[ ] uvicorn main:app --reload starts cleanly with no import errors
[ ] GET /health returns {"status":"ok","db":"connected"}
[ ] POST /trips returns a trip_id
[ ] GET /trips/{id}/stream emits SSE events in terminal
[ ] Graph pauses at city_selection_hitl and emits HITL_REQUIRED event
[ ] POST /trips/{id}/confirm-city resumes the graph successfully
[ ] Remaining SSE events stream after city confirmation
[ ] TRIP_COMPLETE event contains a non-empty trip_pitch
[ ] GET /admin/serpapi-usage returns current month's call count
[ ] LangSmith dashboard shows a trace for the integration test run
[ ] All 3 integration test assertions pass
[ ] No unhandled exceptions in uvicorn logs during a full run
```
