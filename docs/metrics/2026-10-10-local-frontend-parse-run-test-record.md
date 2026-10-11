# Local Frontend Parse Run Test Record — 2026-10-10

## Scope

This record covers P1-9c only: Parse Run submission from a Job, session-local run
tracking, non-terminal polling, terminal status display, and structured
requirements rendering.

- Branch: `codex/p1-3b-embedding-holdout`
- Base HEAD: `96774d5`
- Backend schema, migrations, authorization, worker, or API changes: none
- Provider calls or holdout access: none
- P1-8 and existing backend Parse Run test rerun: none

## Verification

| Check | Result |
|---|---|
| ESLint | passed |
| Strict TypeScript | passed |
| Vitest | 19 passed across 8 files |
| Production dependency audit | 0 vulnerabilities |
| Optimized Next.js build | passed; 12 routes generated |
| Git whitespace check | passed |

New behavior tests verify:

- the same idempotency key is reused after a 503 submission failure;
- a succeeded run displays its saved requirement category, skill, and text;
- a failed run displays `PARSER_OUTPUT_INVALID` and no requirements.

## Boundaries

- This is frontend component and request-contract evidence, not P1-10 local
  full-stack acceptance.
- Parse Run state is retained for the current mounted Job card only. The public
  API has no run-list route, so page-refresh recovery is not claimed.
- Analysis Runs, Action Items, and live Dashboard data remain for later P1-9
  slices.
- The P1-9a development-only dependency-audit limitation remains unchanged;
  production dependencies report zero vulnerabilities.
