# ADR-040: CV Import And Assisted Job Discovery

## Status

Accepted

## Context

Manual Experience and Job entry is reliable but makes the first-use workflow
slow. Importing CV content and discovering public job listings can reduce that
friction, but both inputs are untrusted and may be incomplete. The feature must
preserve user ownership, evidence traceability, worker isolation, deterministic
tests, and explicit review before durable product resources are created.

Google Docs links require OAuth, Drive permissions, export APIs, and credential
lifecycle management. Legacy office files need conversion support, while scanned
PDFs need a separate OCR trust and quality boundary. A real job-search provider
also requires a provider choice, terms review, credentials, and a live-call
budget.

## Decision

- Accept text PDFs, DOCX, DOC, ODT, RTF, UTF-8 TXT, and Markdown up to 5 MiB.
  Detect content signatures instead of trusting the filename or media type.
- Parse PDF and DOCX directly. Convert DOC, ODT, and RTF with headless
  LibreOffice in the worker image only. Reject encrypted PDFs, suspicious ZIP
  packages, invalid encodings, and files with no usable text. OCR is deferred.
- Store the original bytes, normalized text, durable lifecycle, failure code,
  and source-grounded Experience drafts in PostgreSQL. Every generated draft
  keeps exact source offsets and quotes.
- Keep drafts separate from formal Experiences and Jobs. Only an explicit user
  confirmation creates a formal resource. Confirmation locks the draft and is
  replay-safe; Experience confirmation also creates its embedding run in the
  same transaction.
- Keep manual Experience and Job creation unchanged.
- Run job discovery through a worker-side `JobSearchProvider` boundary. The
  current implementation is deterministic fake-only. Results persist provider
  identity, source URL, and `observed_at`.
- Never expand a result summary into a job description. When the provider does
  not return the complete description, require the user to paste it before
  confirmation.
- Support Google Docs in this version by instructing the user to export DOCX or
  PDF and upload it. Do not add Google OAuth, Drive import, generic URL fetching,
  broad scraping, per-user provider keys, or automatic applications.

## Alternatives Considered

- Direct Google Docs import: deferred because it adds external account and
  credential lifecycle scope unrelated to the core reliability proof.
- Separate parsers for every legacy format: rejected because LibreOffice gives
  one mature conversion boundary with less format-specific code.
- OCR in the first version: deferred because scanned-document confidence and
  correction need a separate review design.
- API-side extraction or search: rejected because expensive and unreliable work
  belongs behind the existing worker boundary.
- Generate missing job descriptions from summaries: rejected because it would
  fabricate source material.

## Consequences

The worker image is larger because it contains LibreOffice, while the API image
does not. Original CV bytes remain durable so extraction is reproducible; this
also means retention and deletion currently follow the owning user's database
lifecycle rather than an automatic cleanup schedule.

The fake search results prove contracts and the product loop, not real listing
coverage, freshness, provider reliability, or terms compliance. Selecting one
real provider remains a separate approved change.

## Verification Or Evidence

- Unit tests cover type detection, invalid input, DOCX extraction, suspicious
  archives, result validation, and deterministic fake search.
- PostgreSQL integration tests cover review-before-write, object ownership,
  incomplete-description blocking, replay-safe confirmation, and concurrent
  Experience confirmation.
- Frontend component tests cover upload and search forms.
- The isolated fake-provider browser acceptance covers upload, worker
  extraction, Experience confirmation, job search, Job confirmation, parsing,
  Analysis, Action Items, and Dashboard state.
- Exact local results and evidence limits are recorded in
  `docs/metrics/2026-10-11-cv-import-job-discovery-test-record.md`.

## Revisit If

- Users regularly need direct Google Docs import.
- Scanned PDFs are common enough to justify an OCR confidence and correction
  workflow.
- One reviewed search provider is selected with an approved credential and
  live-call budget.
- A documented privacy requirement demands shorter raw-file retention.
