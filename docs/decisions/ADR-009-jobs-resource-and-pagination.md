# ADR-009: Jobs Resource Model And Cursor Pagination

## Status

Accepted

## Context

After authentication and the experience library, CareerOps AI needs a target job
resource. Job descriptions are the parent input for later parse runs and
analysis runs.

The product document defines this as `US-003: Save A Target Job Description` and
`UC-003: Save A Job Description`. Without saved jobs, the async AI workflow has
no stable resource to attach to.

## Decision

Add a `jobs` table and `/api/v1/jobs` CRUD endpoints.

The table stores:

- `user_id` with `ON DELETE CASCADE`
- `company`, `title`, and `raw_description`
- `description_hash` derived from normalized raw JD text
- nullable `source_url`, `location`, and `deadline`
- `status` constrained to `saved`, `preparing`, `applied`, `interview`,
  `offer`, `rejected`, or `withdrawn`
- `version` for optimistic locking
- `deleted_at` for soft deletion

All detail, update, and delete queries include `user_id` and `deleted_at IS NULL`
in the database predicate. Cross-user access returns `404 JOB_NOT_FOUND`.

Updates require `If-Match: <version>`. Stale versions return
`409 JOB_VERSION_CONFLICT`; missing or malformed preconditions return
`428 IF_MATCH_REQUIRED`.

Job lists support optional status filtering, bounded `limit`, and cursor
pagination based on `(updated_at, id)`. The supporting partial index is:

```sql
CREATE INDEX idx_jobs_user_status_updated
  ON jobs (user_id, status, updated_at DESC)
  WHERE deleted_at IS NULL;
```

## Alternatives Considered

- Use offset pagination: simpler, but it becomes unstable when rows are inserted
  during pagination and performs poorly on deep pages.
- Make `source_url`, `location`, and `deadline` required: rejected because many
  copied JDs are incomplete or unclear.
- Add parse run and job creation in one change: rejected because saved jobs are a
  resource boundary worth testing before the async workflow exists.
- Hard delete jobs: simpler, but future action items and analysis history need a
  consistent story for archived jobs.

## Consequences

The project now supports the third step in the MVP user flow: saving a target job
description.

The jobs API is intentionally still synchronous and does not parse requirements.
Parsing will be added as a separate run resource so model latency and failures
stay out of the API request path.

The first pagination implementation is functional and indexed, but performance
numbers are not measured yet. Any future README or resume latency claims must be
backed by saved metrics under `docs/metrics/`.

## Verification Or Evidence

Verified locally:

- `.\.venv\Scripts\alembic upgrade head`
- PostgreSQL `\d jobs` shows nullable optional fields, CHECK constraints,
  foreign key, and partial index.
- `.\.venv\Scripts\python -m pytest`
- `.\.venv\Scripts\python -m mypy`
- `.\.venv\Scripts\ruff check .`
- `.\.venv\Scripts\lint-imports`
- Integration tests with `CAREEROPS_RUN_INTEGRATION=1` pass for auth,
  experiences, and jobs.

## Revisit If

Revisit if status transitions need a stricter state machine, if query metrics
show the list index is insufficient, or if parse/analysis history requires a
more explicit archived-job display contract.
