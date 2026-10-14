# CV Import And Assisted Job Discovery Test Record

Date: 2026-10-11

## Scope

Local synthetic verification of multi-format CV normalization, review-only
Experience drafts, deterministic assisted job discovery, editable Job drafts,
and the existing downstream product loop. This is not real-provider, OCR,
performance, cloud, or production evidence.

## Static And Unit Verification

- Ruff: passed for `src`, `tests`, and `migrations`.
- strict mypy: passed for 134 source files.
- import boundaries: both contracts passed.
- backend suite with local PostgreSQL and Redis: 395 passed, 2 skipped. The
  skipped cases retained their explicit real-provider or separate worker-E2E
  gates; no live provider was authorized.
- Alembic fresh upgrade through `202610110001`: passed.
- Alembic model/migration drift check: no new upgrade operations detected.
- frontend ESLint and strict TypeScript: passed.
- frontend Vitest: 16 files and 34 tests passed.
- frontend production build: passed.

The focused PostgreSQL test directly verified that drafts do not write formal
resources before confirmation, cross-user access returns 404, incomplete job
descriptions cannot be confirmed, retries return the same resource, and two
concurrent Experience confirmations create one Experience.

## Container And Browser Verification

Acceptance command:

```powershell
.\scripts\local_full_stack_acceptance.ps1 `
  -RunId 20261011cv5 `
  -PostgresPort 25410 `
  -RedisPort 26310 `
  -ApiPort 28010 `
  -FrontendPort 23010
```

Result:

- fresh migration: passed;
- frontend runtime user: UID 1000;
- parser, embedding, matcher, and job search behavior: fake;
- Chromium flow: passed in 10.7 seconds;
- exact Compose project cleanup: passed.

The browser completed registration, Markdown CV upload, worker extraction,
Experience review and confirmation, fake job search, selection of a result with
no complete description, confirmation blocking, user-supplied full description,
Job confirmation, Parse, Analysis, evidence/gap review, Action Item creation,
application-state update, and Dashboard verification.

The built worker image also converted a disposable RTF document through
headless LibreOffice and returned the expected text. This verifies the shared
LibreOffice conversion path used by DOC, ODT, and RTF; it is not a format-corpus
quality evaluation.

## Failed Attempts That Informed The Final Test

- The default acceptance ports were already occupied. The harness failed before
  creating resources and reported cleanup passed; the verified run used the
  alternate ports above.
- One browser attempt selected an incomplete result by relying on result order.
  The disabled confirmation correctly prevented Job creation. The final test
  selects the result by its description-availability label.
- One browser attempt assumed every fake-search requirement would produce a
  gap. The imported evidence covered both requirements, so the final test uses
  a user-supplied description with one supported and one unsupported skill.

## Evidence Limits

- No real search provider was selected or called.
- No Google OAuth or Drive API was used.
- No scanned-PDF OCR was implemented or evaluated.
- No claim is made about extraction accuracy across arbitrary documents.
- Original CV bytes remain in PostgreSQL until the owning data is deleted; no
  automatic retention scheduler exists.
