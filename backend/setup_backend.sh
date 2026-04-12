#!/bin/bash

# ─────────────────────────────────────────────
#  Squad Planner — backend scaffold (current layout)
# ─────────────────────────────────────────────

set -e

ROOT="backend"

echo ""
echo "  Setting up backend folder structure..."
echo ""

mkdir -p "$ROOT/agent/nodes"
mkdir -p "$ROOT/agent/subgraphs"
mkdir -p "$ROOT/tools"
mkdir -p "$ROOT/db"
mkdir -p "$ROOT/api"
mkdir -p "$ROOT/utils"

# ── Root ────────────────────────────────────
touch "$ROOT/main.py"
touch "$ROOT/config.py"
touch "$ROOT/requirements.txt"

# ── agent/ ──────────────────────────────────
touch "$ROOT/agent/__init__.py"
touch "$ROOT/agent/graph.py"
touch "$ROOT/agent/state.py"

touch "$ROOT/agent/nodes/__init__.py"
touch "$ROOT/agent/nodes/input_parser.py"
touch "$ROOT/agent/nodes/destination_selector.py"
touch "$ROOT/agent/nodes/tool_selector.py"
touch "$ROOT/agent/nodes/budget_analyzer.py"
touch "$ROOT/agent/nodes/hotel_searcher.py"
touch "$ROOT/agent/nodes/fairness_scorer.py"
touch "$ROOT/agent/nodes/output_assembler.py"

touch "$ROOT/agent/subgraphs/__init__.py"
touch "$ROOT/agent/subgraphs/itinerary.py"

# ── tools/ ─────────────────────────────────
touch "$ROOT/tools/__init__.py"
touch "$ROOT/tools/serpapi.py"
touch "$ROOT/tools/google_places.py"
touch "$ROOT/tools/google_routes.py"
touch "$ROOT/tools/open_meteo.py"

# ── db/ ─────────────────────────────────────
touch "$ROOT/db/__init__.py"
touch "$ROOT/db/client.py"
touch "$ROOT/db/checkpointer.py"
touch "$ROOT/db/models.py"

# ── api/ ────────────────────────────────────
touch "$ROOT/api/__init__.py"
touch "$ROOT/api/trips.py"
touch "$ROOT/api/hitl.py"
touch "$ROOT/api/admin.py"

# ── utils/ ──────────────────────────────────
touch "$ROOT/utils/__init__.py"
touch "$ROOT/utils/preference_vectors.py"
touch "$ROOT/utils/neighborhood_cluster.py"
touch "$ROOT/utils/streaming.py"

echo "  Done! Folder structure created under ./$ROOT"
echo ""
