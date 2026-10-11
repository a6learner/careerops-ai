# Local Frontend Resource Workflows Test Record — 2026-10-08

## Scope

This record covers P1-9b only: browser Experience CRUD, Job creation and listing,
cursor pagination, Job status updates, and shared resource error presentation.

- Branch: `codex/p1-3b-embedding-holdout`
- Base HEAD: `96774d5`
- Backend schema, migrations, authorization, or API changes: none
- Provider calls or holdout access: none
- P1-8 test rerun: none

## Verification

| Check | Result |
|---|---|
| ESLint | passed |
| Strict TypeScript | passed |
| Vitest | 16 passed across 7 files |
| Production dependency audit | 0 vulnerabilities |
| Optimized Next.js build | passed; 12 routes generated |
| Git whitespace check | passed |

New behavior tests verify:

- Experience form normalization and POST payload;
- Experience PATCH with the displayed version in `If-Match`;
- Experience delete confirmation and DELETE request;
- Job creation payload and optional-field normalization;
- Job status PATCH with the displayed version in `If-Match`;
- preservation of structured 429 details and `Retry-After`.

## Boundaries

- This is component- and contract-level frontend evidence, not P1-10 browser-driven
  full-stack acceptance.
- Job full-field editing and deletion are not P1-9 product requirements and were
  not added.
- Parse Runs, Analysis Runs, Action Items, and live Dashboard data remain for the
  next P1-9 slices.
- The P1-9a development-only dependency-audit limitation remains unchanged;
  production dependencies report zero vulnerabilities.
