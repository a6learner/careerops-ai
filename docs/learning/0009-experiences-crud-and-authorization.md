# 0009 Experiences CRUD And Object-Level Authorization

## What Changed

This step added the first user-owned business resource:

- `experiences` database table.
- `GET /api/v1/experiences`
- `POST /api/v1/experiences`
- `GET /api/v1/experiences/{experience_id}`
- `PATCH /api/v1/experiences/{experience_id}`
- `DELETE /api/v1/experiences/{experience_id}`

Each experience belongs to one user. The API uses the current-user dependency
from authentication, then repository queries include `user_id` so users can only
see or change their own records.

## Why It Exists

Experiences are the evidence library. Later, job requirements will be matched
against this library. The system must never claim a user has a skill without
traceable evidence, so the evidence objects need ownership, versioning, and
stable content hashes before the AI pipeline exists.

## Failure Modes It Prevents

- User A reading, updating, or deleting User B's experience.
- A stale browser tab overwriting a newer update.
- A deleted experience disappearing from future historical analysis references.
- A future embedding worker reusing an old embedding after meaningful content
  changes.
- A database created on a new machine missing pgvector support.

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

Database pgvector check:

```powershell
docker compose exec -T postgres psql -U careerops -d careerops -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

## What You Must Understand

Level 1: Object-level authorization means checking ownership for each resource,
not just checking that the request has a valid token.

Level 1: Optimistic locking protects against lost updates. The client sends the
version it last saw with `If-Match`; the server rejects the update if the stored
version has changed.

Level 1: Soft deletion keeps history possible. The active product hides deleted
records, but future analysis history can still reference an archived experience.

Level 2: `content_hash` is a deterministic SHA-256 hash of meaningful content.
It tells the future embedding pipeline whether the experience text actually
changed.

Level 2: `vector(1536)` is storage for embedding vectors. It is not populated by
CRUD itself; a later worker will generate embeddings asynchronously.

## Knowledge Check

1. Why should cross-user access to an experience return 404 instead of 403?
2. Why do repository queries include `user_id` instead of fetching by id first
   and checking ownership afterward?
3. What problem does `If-Match` solve when two browser tabs edit the same
   experience?
4. Why do we clear `embedding` when meaningful experience content changes?
5. Why is `content_hash` better than only checking `updated_at` for embedding
   invalidation?
