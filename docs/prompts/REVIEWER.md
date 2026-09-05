# Reviewer Prompt Template

Paste into the reviewing agent (Codex by default — never the agent that wrote the code).
Replace `<N>` and `<BRANCH>`.

---

```
You are performing an independent code review. You did NOT write this code, and your job is to
find what the author missed — not to confirm their work.

READ FIRST:
1. docs/phases/PHASE_<N>.md — the specification this branch was built against. This is the
   contract. Anything claimed but not delivered is a finding.
2. AGENTS.md — repo conventions and hard rules.
3. docs/DECISIONS.md — settled decisions. A deviation from these is a finding; do not
   relitigate the decisions themselves.

THE DIFF:
    git diff main...<BRANCH>

REVIEW IN THIS ORDER:

1. SPEC COMPLIANCE. Walk each objective in PHASE_<N>.md and mark it delivered, partial, or
   missing, citing file:line. Check the out-of-scope list too — work that leaked in is a finding.

2. DOES THE TEST ACTUALLY GATE ANYTHING? Assume the tests were written to pass, not to catch.
   For each one ask: what bug would this fail on? Try to construct a change that breaks the
   feature but keeps the suite green. A test that passes vacuously is worse than no test, because
   it buys false confidence. Say so explicitly if you find one.

3. CORRECTNESS. Trace the real paths, not the happy path: what happens on existing production
   documents that predate this change, on concurrent requests, on a partial failure, on a retry?

4. SECURITY. For every new or changed endpoint: can it be reached without the credential it
   assumes? Can one user reach another user's data? Does any response return more than the caller
   should see? Does any unbounded input reach a paid API, an email send, or an LLM prompt?

5. OPERATIONS. Will this start cleanly against a database that already has real data in it?
   Is anything unbounded — collection growth, retries, fan-out, cost? Are new settings documented
   in .env_example?

RULES:
- Cite file:line for every finding. No finding without a location.
- For each, give a concrete failure scenario: specific inputs or state, and the wrong outcome.
- Rank: MUST FIX (broken, insecure, or contradicts the spec) / SHOULD FIX (real problem, not a
  blocker) / NIT (style or preference).
- Do not fix anything. Report only.
- If you find nothing in a category, say so plainly rather than inventing filler.
- Verify claims by reading the code. Do not trust comments, commit messages, or the PR description.

Finish with a one-line verdict: SHIP, SHIP AFTER MUST-FIX, or DO NOT SHIP.
```
