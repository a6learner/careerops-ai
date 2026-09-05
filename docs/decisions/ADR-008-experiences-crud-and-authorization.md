# ADR-008: Experiences CRUD And Object-Level Authorization

## Status

Accepted

## Context

CareerOps AI needs an experience library before it can match job requirements to
real user evidence. Experiences are user-owned resources and will later be cited
by evidence matching, so the first implementation must establish ownership,
soft deletion, optimistic locking, content hashing, and a place for future
embedding vectors.

The project already has registration, login, signed access tokens, and a
current-user dependency. This makes experiences the first resource that can
exercise object-level authorization.

## Decision

Add an `experiences` table and `/api/v1/experiences` CRUD endpoints.

The table stores:

- `user_id` with `ON DELETE CASCADE`
- `kind` constrained to `project`, `work`, `research`, `course`, or `other`
- `skills` as `text[]`
- `version` for optimistic locking
- `content_hash` for detecting meaningful content changes
- nullable `embedding vector(1536)` for the later retrieval pipeline
- `deleted_at` for soft deletion

All detail, update, and delete queries include `user_id` and `deleted_at IS NULL`
in the database predicate. A user trying to access another user's experience
receives `404 EXPERIENCE_NOT_FOUND`.

Updates require `If-Match: <version>`. A stale version returns
`409 EXPERIENCE_VERSION_CONFLICT`; a missing or malformed precondition returns
`428 IF_MATCH_REQUIRED`.

The migration installs PostgreSQL `vector` with `CREATE EXTENSION IF NOT EXISTS
vector`. The `1536` dimension matches the default output length of
`text-embedding-3-small`, which is the intended low-cost embedding model for the
MVP retrieval path.

## Alternatives Considered

- Store `skills` in a separate normalized table: more flexible long-term, but
  unnecessary for the MVP and heavier for the first CRUD slice.
- Hard delete experiences: simpler, but would break future historical analysis
  references. Soft deletion lets old evidence still be shown as archived.
- Put version in the request body: easier to implement, but `If-Match` expresses
  HTTP optimistic concurrency more directly.
- Defer the `embedding` column: possible, but adding nullable `vector(1536)` now
  makes the later retrieval milestone a smaller schema change and verifies
  pgvector early.

## Consequences

The backend now has its first user-owned business resource and the first direct
authorization matrix test.

The `embedding` column is present but not populated yet. Content changes clear
the embedding value on update so a future worker can regenerate it.

The custom SQLAlchemy `PgVector` type is intentionally small and local. The
project can revisit a dedicated pgvector Python dependency when vector queries
and HNSW indexes are implemented.

## Verification Or Evidence

Verified locally:

- `docker compose up -d postgres`
- `.\.venv\Scripts\alembic upgrade head`
- PostgreSQL reports `vector` extension version `0.8.6`
- `experiences.embedding` has database type `vector`
- `.\.venv\Scripts\python -m pytest`
- `.\.venv\Scripts\python -m mypy`
- `.\.venv\Scripts\ruff check .`
- `.\.venv\Scripts\lint-imports`
- Integration tests with `CAREEROPS_RUN_INTEGRATION=1` pass for auth and
  experiences

## Revisit If

Revisit if the embedding provider changes to a model with a different default
dimension, if we decide to use OpenAI's `dimensions` parameter, or if vector
query implementation benefits enough from adding the dedicated `pgvector`
Python package.
