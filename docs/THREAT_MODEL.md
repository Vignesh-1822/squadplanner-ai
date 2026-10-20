# Phase 0 Threat Model

## Scope and assets

Phase 0 protects authentication, authorization, session lifecycle, trip membership, operational
quota, and transport boundaries. Assets include user email and profile data, budgets and dietary
restrictions, invite codes, trip and itinerary state, LangGraph checkpoints, and paid external API
quota.

Trust boundaries are:

1. Browser to FastAPI over credentialed CORS.
2. FastAPI to MongoDB.
3. LangGraph to Anthropic, SerpAPI, and Google services.
4. The human leader decision at the city-selection interrupt.

## Controls and OWASP mapping

This mapping uses the OWASP Top 10 for LLM Applications 2025 and the OWASP Top 10 for Agentic
Applications 2026.

| Phase 0 control | Threat reduced | OWASP mapping |
|---|---|---|
| Cookie JWT authentication on every private route | Anonymous access to personal trip state and paid operations | LLM02 Sensitive Information Disclosure; ASI03 Identity & Privilege Abuse |
| Identity derived from the token | Ownership spoofing and privilege escalation through request bodies | LLM06 Excessive Agency; ASI03 Identity & Privilege Abuse |
| Member, leader, and admin dependencies | IDOR, unauthorized mutation, HITL hijacking, and quota disclosure | LLM06 Excessive Agency; ASI02 Tool Misuse; ASI03 Identity & Privilege Abuse; ASI09 Human-Agent Trust Exploitation |
| Invite code required to join; preferences require membership | Unauthorized entry through a guessed trip identifier or join bypass | ASI03 Identity & Privilege Abuse |
| 24-hour expiry and `token_version` revocation | Reuse of stolen or logged-out sessions | LLM02 Sensitive Information Disclosure; ASI03 Identity & Privilege Abuse |
| HttpOnly/SameSite cookie, configurable Secure flag, explicit credentialed CORS origins | Token theft and cross-origin credential exposure | LLM02 Sensitive Information Disclosure; ASI03 Identity & Privilege Abuse |
| Per-IP authentication limits and per-user costly-operation limits | Credential attacks, denial of service, and model/API cost abuse | LLM10 Unbounded Consumption; ASI08 Cascading Failures |
| Cache TTL and query/uniqueness indexes | Unbounded storage growth and inconsistent authorization lookups | LLM10 Unbounded Consumption; ASI08 Cascading Failures |
| SerpAPI usage collection and preserved migration | Quota reset through cache expiry and uncontrolled paid calls | LLM10 Unbounded Consumption; ASI02 Tool Misuse |
| Leader-only city confirmation and refinement | Unauthorized human approval or shared-state mutation | LLM06 Excessive Agency; ASI09 Human-Agent Trust Exploitation |
| Route-table sweep and role matrix | Regression where a future route is accidentally public or under-authorized | ASI03 Identity & Privilege Abuse |

## Residual risks

- Rate-limit state is in memory. It resets on restart and is not shared across multiple instances.
- Anyone holding a valid invite code may join; invite-email allow-list enforcement is a product
  decision still outstanding.
- A stolen cookie remains usable until expiry or a token-version bump.
- The public invite preview exposes limited trip metadata by design.
- Upstream model, map, travel-search, and email providers remain external trust dependencies.

## Explicitly deferred

Prompt-injection defenses, input sanitization, model-output validation, memory-poisoning controls,
and tool-result content controls are Phase 2 work. Phase 0 does not claim to mitigate LLM01 Prompt
Injection, ASI01 Agent Goal Hijack, ASI06 Memory & Context Poisoning, or the related supply-chain
and code-execution categories.
