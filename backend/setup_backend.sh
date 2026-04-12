#!/bin/bash

# ─────────────────────────────────────────────
#  Trip Planner AI Agent - Backend Scaffold
# ─────────────────────────────────────────────

set -e

ROOT="backend"

echo ""
echo "  Setting up backend folder structure..."
echo ""

# ── Root files ──────────────────────────────
mkdir -p "$ROOT"

touch "$ROOT/main.py"
touch "$ROOT/requirements.txt"
touch "$ROOT/.env"

# ── agent/ ──────────────────────────────────
mkdir -p "$ROOT/agent/nodes"
mkdir -p "$ROOT/agent/tools"

touch "$ROOT/agent/__init__.py"
touch "$ROOT/agent/graph.py"
touch "$ROOT/agent/state.py"

NODES=(
  "parse_input.py"
  "select_destination.py"
  "search_flights.py"
  "search_hotel.py"
  "fetch_activities.py"
  "build_itinerary.py"
  "plan_routes.py"
  "check_weather.py"
  "compute_fairness.py"
  "assemble_output.py"
  "parse_refinement.py"
)

touch "$ROOT/agent/nodes/__init__.py"
for f in "${NODES[@]}"; do
  touch "$ROOT/agent/nodes/$f"
done

TOOLS=(
  "google_places.py"
  "google_maps.py"
  "serpapi_flights.py"
  "serpapi_hotels.py"
  "weather.py"
  "llm.py"
)

touch "$ROOT/agent/tools/__init__.py"
for f in "${TOOLS[@]}"; do
  touch "$ROOT/agent/tools/$f"
done

# ── api/ ────────────────────────────────────
mkdir -p "$ROOT/api/routes"
mkdir -p "$ROOT/api/middleware"

touch "$ROOT/api/__init__.py"
touch "$ROOT/api/routes/trip.py"
touch "$ROOT/api/routes/auth.py"
touch "$ROOT/api/routes/user.py"
touch "$ROOT/api/middleware/auth.py"

# ── data/ ───────────────────────────────────
mkdir -p "$ROOT/data"

touch "$ROOT/data/destinations_db.json"
touch "$ROOT/data/scoring.py"

# ── db/ ─────────────────────────────────────
mkdir -p "$ROOT/db"

touch "$ROOT/db/__init__.py"
touch "$ROOT/db/connection.py"
touch "$ROOT/db/models.py"

# ── tests/ ──────────────────────────────────
mkdir -p "$ROOT/tests"

touch "$ROOT/tests/test_agent.py"
touch "$ROOT/tests/test_tools.py"
touch "$ROOT/tests/test_scoring.py"

# ── Done ────────────────────────────────────
echo "  Done! Folder structure created under ./$ROOT"
echo ""
echo "  To get started:"
echo "    cd $ROOT"
echo "    python -m venv venv && source venv/bin/activate"
echo "    pip install -r requirements.txt"
echo ""