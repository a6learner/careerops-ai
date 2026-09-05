# 0010 Jobs CRUD And Cursor Pagination

## What Changed

This step added the target job resource:

- `jobs` database table.
- `GET /api/v1/jobs`
- `POST /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `PATCH /api/v1/jobs/{job_id}`
- `DELETE /api/v1/jobs/{job_id}`

Job records belong to the current user, store raw JD text, allow unclear optional
metadata to be missing, and support application statuses such as `saved`,
`preparing`, and `applied`.

## Why It Exists

Jobs are the second main input to the product. Experiences answer "what evidence
does the candidate have?" Jobs answer "what target role are we preparing for?"

The later parse and analysis workflow should attach to a saved job, not a loose
string passed to an AI endpoint.

## Failure Modes It Prevents

- One user reading or changing another user's target jobs.
- A stale browser tab overwriting a newer job status or JD edit.
- Optional metadata blocking users from saving incomplete but useful JDs.
- Deep or changing job lists becoming unstable under offset pagination.
- Future parse runs lacking a stable parent resource.

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

Inspect the table:

```powershell
docker compose exec -T postgres psql -U careerops -d careerops -c "\d jobs"
```

## What You Must Understand

Level 1: A job is a resource, not just an argument to `POST /analyze`. This lets
the system store status, history, parsed requirements, analysis runs, and action
items around the same stable object.

Level 1: Cursor pagination uses the last row from the previous page to request
the next page. This avoids the instability of offset pagination when new rows
are inserted.

Level 1: Object-level authorization is repeated for jobs: every detail, update,
and delete query includes the current user's `user_id`.

Level 2: `description_hash` is derived from normalized raw JD text. Later, it can
help decide whether existing parsed requirements are still valid or whether the
JD must be parsed again.

Level 2: Optional fields are a product decision reflected in the schema. JDs are
often incomplete, so `source_url`, `location`, and `deadline` may be null.

## Knowledge Check

1. Why is a saved job a better parent for parse runs than a direct
   `POST /analyze` request with raw text?
2. Why does cross-user access to a job return 404?
3. What problem does `(updated_at, id)` solve in cursor pagination?
4. Why should `deadline` be nullable for copied job descriptions?
5. Why can we add performance claims about pagination only after saving measured
   evidence under `docs/metrics/`?
