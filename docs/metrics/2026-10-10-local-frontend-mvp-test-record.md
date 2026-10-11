# Local Frontend MVP Test Record — 2026-10-10

## Scope

This record closes P1-9 Local Frontend MVP at the component and request-contract
level. It covers registration/login, Experience CRUD, Job creation/list/status,
Parse and Analysis submission/polling, requirements, grounded evidence and gaps,
Action Item management, Dashboard counts, and required error states.

- Branch: `codex/p1-3b-embedding-holdout`
- Base HEAD: `96774d5`
- Backend schema, migrations, authorization, worker, or API changes: none
- Provider calls or holdout access: none
- P1-8/backend full-suite rerun: none

## Verification

| Check | Result |
|---|---|
| ESLint | passed with zero warnings |
| Strict TypeScript | passed |
| Vitest | 27 passed across 12 files |
| Production dependency audit | 0 vulnerabilities |
| Optimized Next.js build | passed; 12 routes generated |
| Git whitespace check | passed |

The final suite directly covers:

- HttpOnly session-cookie flags, exact-origin mutation checks, proxy path/header
  allowlists, login, registration, and structured errors;
- Experience create/edit/delete and Job create/status update with backend concurrency
  headers;
- Parse idempotency retry, non-terminal/terminal presentation, requirements, and
  durable failure display;
- Analysis grounded quote display, safe negative gaps, durable failure display,
  and gap-provenance Action Item creation;
- manual Action Item creation, stable retry keys, and versioned title/status updates;
- Dashboard values returned by the real API contract;
- distinct 409 analysis-precondition and 429 retry guidance.

## Boundaries

- P1-9 is locally implementation- and component-test-complete. This is not a claim
  that P1-10 browser-driven full-stack acceptance has passed.
- Parse and Analysis run identity is session-local because the public API has no
  run-list/latest route. Refresh recovery is not claimed.
- Job creation options on the Action Item form use the 100-item API maximum; gap
  creation remains available directly from the relevant Analysis result.
- The frontend is not yet part of the Compose deployment topology.
- The documented P1-9a development-only dependency advisory remains; production
  dependencies report zero vulnerabilities.
