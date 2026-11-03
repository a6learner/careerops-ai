# ADR-045: Latest-Run Lookup And Dashboard Focus Reads

## Status

Accepted on 2026-10-29 as an additive public API change approved by the author.

## Context

Parse Runs and Analysis Runs could only be read by ID. The frontend kept the IDs
in component state, so reloading a job lost its parsed requirements and evidence
even though both were durable in PostgreSQL. The dashboard returned status
counts only, so it could not answer "what is due soon" or "what should I do
next" although jobs already store deadlines.

## Decision

Add three owner-scoped read endpoints. None changes existing endpoints, writes,
schemas or migrations.

- `GET /api/v1/jobs/{job_id}/parse-runs/latest` returns the newest Parse Run for
  an owned job, ordered by `created_at DESC, id DESC`.
- `GET /api/v1/jobs/{job_id}/analysis-runs/latest?parse_run_id=...` returns the
  newest Analysis Run for that job *and* that Parse Run. The parameter is
  required so the evidence shown always belongs to the requirements shown; an
  analysis of an older parse is never paired with a newer parse.
- Both return `404 JOB_NOT_FOUND` for a missing, deleted or foreign job, and
  `404 PARSE_RUN_NOT_FOUND` / `404 ANALYSIS_RUN_NOT_FOUND` when the owned job has
  no matching run. The frontend treats only the run-level code as "no run yet".
- `GET /api/v1/dashboard/focus` returns at most five rows each of:
  - upcoming deadlines: active jobs with `deadline >= today (UTC)`, excluding
    `rejected` and `withdrawn`, ordered by deadline;
  - recently updated active jobs;
  - open action items on active jobs, `doing` before `todo`, newest first.

The focus read is deliberately uncached. `/dashboard/summary` keeps its Redis
cache and invalidation paths unchanged; adding the focus lists to that cache
would widen the set of writes that must invalidate it (for example deadline and
title edits) for a few small indexed reads.

No migration was added. Parse Runs already have
`idx_parse_runs_user_job_created (user_id, job_id, created_at DESC)`. Analysis
Runs are filtered through the `(user_id, job_id, …)` prefix of
`uq_analysis_runs_user_job_idempotency`; one job has few runs, so the sort is
over a handful of rows. This was not benchmarked.

## Alternatives considered

- **Store run IDs in browser storage.** Rejected: storage is per device, goes
  stale after logout, and duplicates state PostgreSQL already holds.
- **Embed the latest run summary in `GET /jobs/{id}`.** Rejected for now: it
  widens a core contract and couples every job read to run queries.
- **A run history list endpoint.** Not needed by any current screen.
- **Use the browser's local date for "today".** Rejected for the server query
  because user time zones are not stored. The response returns the UTC `today`
  so the frontend counts days from the same date. A deadline can therefore look
  one day off near midnight for users far from UTC.

## Consequences

- Job pages survive reloads and new sessions without re-running model work.
- The dashboard shows next actions without new persistence.
- Three more read paths must keep their authorization tests.

## Verification or evidence

- Unit tests: `tests/test_parse_run_service.py`,
  `tests/test_analysis_run_service.py`, `tests/test_dashboard_service.py`.
- PostgreSQL integration test:
  `tests/integration/test_latest_runs_and_focus_postgres.py` covers ordering,
  the two 404 codes, cross-user access, the required query parameter, and
  focus filtering of past, closed, archived and foreign rows.
- Frontend tests restore a run after reload without submitting work again.
- Recorded in `docs/metrics/2026-10-29-ui-polish-test-record.md`.
