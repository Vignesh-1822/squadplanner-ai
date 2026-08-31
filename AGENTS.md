# AGENTS.md — SquadPlanner AI

Instructions for any AI coding agent working in this repository.

## What this is

A group-trip planning product. A squad of 1–8 people each submit budget, origin airport, dietary
restrictions, preference sliders and availability windows; a LangGraph agent pipeline scores US
destinations, pauses for a human decision, fetches live travel data, builds a day-by-day itinerary,
and streams progress over SSE. Completed trips accept natural-language refinements that re-enter the
graph at the affected node.

- `backend/` — FastAPI + LangGraph. **This is the source of truth for behaviour.**
- `frontend/` — React 18 + Vite. **Owned by Vignesh. Do not modify** (see Hard rules).
- `showcase/` — an older demo app, ours, being retired in Phase 7. Do not build on it.
- `backend/debug_ui/` — our manual test harness, served at `/debug`. Ours; edit freely.

**Shared-file warning:** `backend/api/trips.py` is the most contested file in the repository —
Vignesh has committed to it six times to add endpoints for his pages. Keep changes there tight and
merge upstream promptly.

## Hard rules

1. **Never modify anything under `frontend/`.** Vignesh owns that directory entirely, including
   `frontend/src/services/`. It is currently byte-identical to the upstream repo and must stay that
   way. API changes are communicated by editing `docs/FRONTEND_CONTRACT.md` — never the JavaScript.
   `showcase/` and `backend/debug_ui/` are ours and may be edited freely.
2. **Never read, print, echo or commit `backend/.env`.** Use `backend/.env_example`. If you need a
   new setting, add it to `.env_example` and to `backend/config.py`.
3. **Work to the phase spec.** The current phase lives in `docs/phases/PHASE_<N>.md`. If the work
   diverges from that spec, stop and say so — do not silently expand scope.
4. **Do not commit generated files**: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `tests/artifacts/`,
   `venv/`, `node_modules/`, `.DS_Store`.
5. **Do not run the live integration test** (`tests/test_integration.py`) — it is gated behind
   `RUN_LIVE_INTEGRATION=true` because it spends real Anthropic, SerpAPI and Google quota.

## Commands

```bash
# from backend/
./venv/bin/python -m pytest tests/ -q          # deterministic suite (no network, no DB)
./venv/bin/python -m uvicorn main:app --reload # dev server on :8000
./venv/bin/python -c "import main"             # fastest import/wiring smoke check
```

The virtualenv is `backend/venv/`. Use `./venv/bin/python`, not a bare `python`.

## Architecture notes an agent will need

- **The orchestrator graph** is `agent/graph.py` — 11 nodes plus an itinerary subgraph
  (`agent/subgraphs/itinerary.py`), with conditional retry edges for budget pressure and fairness
  failure. It is compiled with a MongoDB checkpointer so `interrupt()` can suspend the run to
  durable storage and resume on a later HTTP request.
- **Routes** are mounted under `/api` in `main.py`. `api/trips.py` and `api/squad.py` both use the
  `/trips` prefix and together form one logical resource.
- **Auth** is a JWT in an httpOnly cookie. `api/middleware/auth.py::get_current_user` is the
  dependency; it already loads the full user document on every request.
- **Mongo** is accessed through `db/client.py::get_collection`. There is no ORM.
- **All LLM calls** go through `config.py::get_llm()`.

## Style

- Match the surrounding code: type hints on function signatures, `async def` throughout the request
  path, module docstrings, and comments that explain *why* rather than *what*.
- Pydantic models for request and response bodies.
- Raise `HTTPException` with a `detail` string written for a human — those strings surface in the UI.
- Keep new modules small. `agent/subgraphs/itinerary.py` at 1,330 lines is the anti-pattern here,
  not the template.

## Testing

- Deterministic tests must run with **no network and no database**. Use
  `app.dependency_overrides` and fakes rather than a live Mongo.
- Anything needing real services goes behind an environment flag, following the pattern in
  `tests/test_integration.py`.
