# SquadPlanner Roadmap

Full audit and reasoning: **https://claude.ai/code/artifact/bce3dcff-8a5b-4eea-ac81-c516a2d081e2**

This file is the working checklist. The dossier explains *why* each item is here, with sources.

Goal: a hiring manager concludes "this person ships production multi-agent systems," **and** a real
group can use the product. Constraint: free / near-free tiers.

---

## Phase 0 — Close the doors  ·  BLOCKS EVERYTHING

Eight endpoints have no authentication. All are live on the deployed demo.

- [ ] `GET /api/trips` — **dumps every trip in the DB**; `?email=` enumerates any user. Delete the
      query param, derive the user from the token, add pagination
- [ ] `POST /api/trips/{id}/refine` — **unauthenticated free text into an LLM prompt on a stranger's
      trip**. Auth + membership check
- [ ] `POST /api/trips` — unauthenticated trip creation that **sends invite emails**. Open mail relay
- [ ] `GET /api/trips/{id}` · `/result` · `/stream` — IDOR on emails, budgets, dietary data
- [ ] `POST /api/trips/{id}/confirm-city` — anyone can hijack the HITL decision (OWASP LLM06)
- [ ] `GET /api/admin/serpapi-usage` — needs an admin guard
- [ ] `auth.py:34` `secure=False` → environment-driven
- [ ] `main.py:23` CORS hardcoded to localhost → env var (production origin currently blocked)
- [ ] `slowapi` rate limits: per-IP on auth, per-user on generate/refine
- [ ] Mongo indexes: `trip_id`, `invite_code`, `created_by`; **TTL index on `api_cache`** (grows forever)
- [ ] JWT revocation — 7-day token, logout only clears the cookie
- [ ] `docs/THREAT_MODEL.md` mapped to OWASP LLM Top 10 + Agentic Top 10

## Phase 1 — Make it measurable

- [ ] Langfuse (Docker self-host or free cloud) — trace every node, tool call, LLM call
- [ ] Golden set ~40 cases from `tests/demo_input_cases.json` + `manual_cases.json`
- [ ] Deterministic scorers: budget, dietary, avoided categories, day count, geo sanity, flight alignment
- [ ] LLM-as-judge (stronger model than the planner) for coherence, fairness, pitch quality
- [ ] **Trajectory evals** — nodes run, retry loops fired, tool args valid
- [ ] Token + cost per node, persisted on the trip, shown in the UI
- [ ] Nightly run via the Batches API (50% cost)
- [ ] Fix the 2 failing tests in `test_preference_constraints.py` (stale `CreateTripRequest` shape)
- [ ] Delete or fill the 3 empty test files: `test_agent.py`, `test_scoring.py`, `test_tools.py`

## Phase 2 — Harden the model boundary

- [ ] Replace 6 `json.loads(_strip_json_fences(...))` sites with `.with_structured_output()` + repair retry
      — `output_assembler.py`, `preference_constraints.py`, `destination_selector.py`, `subgraphs/itinerary.py`
- [ ] Input guardrails on `preference_notes` / `group_notes` / refinement text
- [ ] Output guardrail: explicit pass/fail itinerary validation layer
- [ ] Venue validity: check Places `business_status` + `opening_hours` against the scheduled day

## Phase 3 — Ground it (RAG)

- [ ] Corpus: Wikivoyage (CC-BY-SA) + NPS + tourism boards → few thousand chunks
- [ ] Hybrid retrieval — BM25 + dense, RRF fusion, cross-encoder rerank (top-50 → top-5)
- [ ] Ground 3 nodes: destination rationale **with citations**, itinerary pacing, constraint resolution
- [ ] Agentic re-retrieval (self-RAG / corrective RAG) when a claim isn't supported
- [ ] Retrieval evals: precision@k, faithfulness, citation accuracy
- [ ] Publish **venue validity rate** before/after
- [ ] Chroma or FAISS on disk = $0

## Phase 4 — Genuinely multi-agent

- [ ] **Advocate agent per traveler** (parallel fan-out, disjoint context) + **Negotiator**, max 2 rounds
- [ ] Log every objection — "whose preference lost and why" is the demo moment
- [ ] Critic agent with structured revision notes
- [ ] Model routing by node (Haiku for extraction, stronger for planning/critic)
- [ ] Prompt caching on the stable prefix; verify `usage.cache_read_input_tokens`
- [ ] Publish before/after cost per trip

## Phase 5 — Memory

- [ ] Per-user profile: semantic (dietary), episodic (accepted edits), procedural (pacing habits)
- [ ] Consolidation, not just accumulation

## Phase 6 — Durable execution

- [ ] Move graph execution out of the SSE request (`utils/streaming.py:86`) into a worker
- [ ] Resumable streams — reconnect and replay from the checkpoint (the checkpointer already persists state)
- [ ] Idempotency keys on emails and paid API calls
- [ ] Dead-letter queue + retry policy

## Phase 7 — Product

- [ ] **Group voting** at the HITL pause (currently leader-only)
- [ ] **Settle-up** built on the existing fairness scoring
- [ ] Bookable deep links from SerpAPI data already fetched
- [ ] `.ics` export + shareable read-only trip link
- [ ] Email nudges for members who haven't submitted preferences
- [ ] Mobile-responsive itinerary — *Vignesh*

## Phase 8 — Legibility

- [ ] `docker-compose.yml`: backend + Mongo + Langfuse
- [ ] GitHub Actions: deterministic tests + eval suite per PR
- [ ] Architecture diagram generated from the compiled graph
- [ ] README rewrite: what it is → diagram → agent roster → evals → cost → demo GIF → setup
- [ ] Resolve `showcase/` vs `frontend/`
- [ ] Split `agent/subgraphs/itinerary.py` (1,330 lines, ~50 helpers) into clustering / planner / routing / validation

## Stretch — after Phase 0 only

- [ ] Expose SquadPlanner as an **MCP server** so a trip can be planned from inside Claude/ChatGPT
