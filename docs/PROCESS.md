# Development Process

The working agreement for the SquadPlanner SOTA improvement plan.
Route and rationale: `docs/ROADMAP.md` → the dossier linked at its top.

## Roles

| Role | Who | Does |
|---|---|---|
| **Orchestrator** | Claude Code (Opus 5), one long-running chat | Explains each phase, negotiates scope, writes `docs/phases/PHASE_N.md`, writes the kickoff prompt, reads the finished branch |
| **Implementer** | Cursor / Claude Code / Codex — assigned per phase by task shape | Plans in plan mode, implements sub-phase by sub-phase |
| **Reviewer** | A different agent from the implementer, every time | Hostile-reads the plan before coding; reviews the PR diff after |

**Never let the same agent implement and review.** A model shares its own blind spots and
rationalises its own choices; a different model family genuinely doesn't.

## The loop, per phase

1. **Explain** — orchestrator walks the phase intuitively. No code yet.
2. **Negotiate** — Manoj accepts / rejects / modifies. Rejections get logged in `docs/DECISIONS.md`.
3. **Commit the spec** — orchestrator writes `docs/phases/PHASE_N.md`: objectives, out-of-scope,
   success criteria (executable), and sub-phase split. **This file is committed to the repo.**
4. **Hostile read** — reviewer agent reads `PHASE_N.md` and tries to break the *spec* before any
   code exists. Cheap; catches spec bugs while they're still free.
5. **Implement** — `git checkout -b phase-N-<slug>`. Implementer works sub-phase by sub-phase,
   plan mode before each.
6. **Verify** — run the phase's success-criteria command. It passes or it doesn't.
7. **Review** — reviewer agent reviews the PR diff against `PHASE_N.md`.
8. **Report back** — tell the orchestrator the **branch name**. It reads the branch itself.

## Rules for every agent

- The spec is `docs/phases/PHASE_N.md`. If the work diverges from it, stop and say so — don't
  silently expand scope.
- **Never modify `frontend/`.** Vignesh owns it. `docs/FRONTEND_CONTRACT.md` is the contract.
- **Never read or print `backend/.env`.** Use `backend/.env_example`.
- Success criteria are commands, not prose. "Done" means the command passes.
- One branch per phase, one PR per phase.

## Success criteria must be executable

Not *"all endpoints require authentication"* — that's an opinion an agent can talk itself into.

Instead: `pytest backend/tests/test_authz.py` — a test that hits every route anonymously and
asserts `401`. Done becomes a command with an exit code.

This matters most from Phase 1 onward, where the deliverable *is* the measurement harness. After
Phase 1 lands, success criteria for later phases stop being prose and become eval scores — the
process upgrades itself.

## Agent assignment

Rotate by **task shape**, not on a schedule. Rotating for its own sake costs a context rebuild
every time.

| Phase | Shape | Implementer | Reviewer |
|---|---|---|---|
| 0 · Security | Mechanical, many files | **Cursor** (Pro+ expiring) | Codex |
| 1 · Evals | Scaffolding + judgment | Cursor, then Claude Code | Codex |
| 2 · Harden boundary | Mechanical, 6 known sites | Cursor / Codex | Claude Code |
| 3 · RAG | Novel architecture | **Claude Code (Opus)** | Codex |
| 4 · Multi-agent | Novel architecture | **Claude Code (Opus)** | Codex |
| 5 · Memory | Design-heavy | Claude Code | Codex |
| 6 · Durable execution | Infra reasoning | Claude Code | Codex |
| 7 · Product features | Broad, mostly mechanical | Cursor / Codex | Claude Code |
| 8 · Packaging | Mechanical | Codex | Cursor |

Reserve Claude Pro for orchestration and the two architecture phases. Don't spend Opus limits on
work Cursor or Codex can do.

## Repo conventions

- `AGENTS.md` at the root — read natively by Cursor, Codex, and ~15 other agents; stewarded by the
  Linux Foundation's Agentic AI Foundation. `CLAUDE.md` is a one-line `@AGENTS.md` import, because
  Claude Code still reads `CLAUDE.md`.
- `docs/phases/PHASE_N.md` — the spec for each phase.
- `docs/DECISIONS.md` — one entry per rejected or modified idea, with the reason. Doubles as an
  ADR log, which is portfolio material in its own right.
