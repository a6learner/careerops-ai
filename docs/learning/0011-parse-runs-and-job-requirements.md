# 0011 Parse Runs And Job Requirements

## What Changed

This step added the first structured job-description analysis resource:

- `parse_runs` table.
- `job_requirements` table.
- `POST /api/v1/jobs/{job_id}/parse-runs`
- `GET /api/v1/jobs/{job_id}/parse-runs/{parse_run_id}`

The POST endpoint requires `Idempotency-Key` and returns `202 Accepted`. The
current implementation uses a deterministic local fake parser instead of a real
LLM or worker.

## Why It Exists

A saved job is still just raw text. Before the system can match requirements to
experience evidence, it needs explicit requirement rows.

The parse run is a resource because parsing has identity, status, inputs,
versioned parser metadata, possible failures, and historical results. It is not
just a hidden helper function.

## Failure Modes It Prevents

- Repeated submit clicks creating duplicate parse runs.
- Users reading parse runs for jobs they do not own.
- Parsed requirements being stored without a link back to the raw JD text.
- Future analysis runs depending on unstructured raw text instead of stable
  requirement rows.
- API tests depending on a real LLM or network call.

## How To Verify It

Default local checks:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

PostgreSQL integration checks:

```powershell
docker compose up -d postgres
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python -c "import os, pytest; os.environ['CAREEROPS_RUN_INTEGRATION']='1'; raise SystemExit(pytest.main(['tests/integration']))"
```

Inspect the tables:

```powershell
docker compose exec -T postgres psql -U careerops -d careerops -c "\d parse_runs"
docker compose exec -T postgres psql -U careerops -d careerops -c "\d job_requirements"
```

## What You Must Understand

Level 1: `202 Accepted` means the request created or reused work that has a
separate resource identity. It does not mean the API route should block on an
unreliable external model call.

Level 1: Idempotency protects users and the backend when the same submit action
is repeated. The same user and same `Idempotency-Key` return the same parse run.

Level 1: Source spans connect each structured requirement back to raw JD text.
This is the first anti-hallucination layer for parsing.

Level 2: The current fake parser is deterministic. It exists to make API,
database, and authorization behavior testable before the real worker and LLM
adapter are introduced.

Level 2: `parse_runs.user_id` is redundant with `jobs.user_id`, but useful for
authorization filters and future run list queries.

## Knowledge Check

1. Why is a parse run a resource instead of a direct `POST /analyze` helper?
2. What does `Idempotency-Key` prevent when a user double-clicks submit?
3. Why should every parsed requirement keep a source span into the raw JD?
4. Why is a deterministic fake parser better than a real LLM for CI tests?
5. What must change in the next worker milestone while preserving the API
   contract?
