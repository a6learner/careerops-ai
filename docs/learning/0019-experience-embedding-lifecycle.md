# 0019 Experience Embedding Lifecycle

## What Changed

Experience create and update now persist a version-bound embedding run. A worker
uses a deterministic fake provider to produce a validated 1536-dimensional vector,
then atomically writes the vector and its content/model/input provenance.

The system also has stale-run recovery, queued redispatch, and reconciliation for
Experiences created before this lifecycle existed. No public API response changed.

## Why It Exists

An embedding is derived data. It can be recomputed, but it must never be treated as
valid for Experience content other than the exact version that produced it.
PostgreSQL therefore stores task identity and lifecycle while Redis remains only a
delivery mechanism.

## Failure Modes It Prevents

- A delayed worker overwriting a vector after the user edits the Experience.
- A recovered attempt accepting completion from the worker for the old attempt.
- Duplicate Redis messages creating duplicate durable runs.
- Redis failure losing accepted work.
- A cross-user mutation superseding another user's active embedding work.
- A wrong-dimension or non-finite vector reaching pgvector.
- Background embedding completion causing false `If-Match` conflicts or changing
  Analysis Run input fingerprints.
- Soft-deleted Experience content remaining eligible as a current vector.

## How To Verify It

Run offline checks:

```powershell
.\.venv\Scripts\python -m pytest -ra
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

Run infrastructure integration tests without a real model:

```powershell
$env:CAREEROPS_RUN_INTEGRATION='1'
$env:CAREEROPS_REDIS_URL='redis://127.0.0.1:6379/0'
.\.venv\Scripts\python -m pytest tests/integration -ra
Remove-Item Env:CAREEROPS_RUN_INTEGRATION
Remove-Item Env:CAREEROPS_REDIS_URL
```

Recover and backfill embedding work:

```powershell
.\.venv\Scripts\python -m careerops.workers.embedding_recovery
```

## What You Must Understand

Level 1:

- At-least-once delivery allows duplicate messages; conditional claiming and
  attempt fencing protect persisted results rather than promising one computation.
- `version` identifies the accepted business revision, while `content_hash`
  proves the meaningful content. Both must match before writeback.
- Lock ordering is run before Experience for both worker completion and user
  mutation, avoiding an inverse-lock deadlock.
- Dispatch after commit can fail without losing work because recovery reads queued
  state from PostgreSQL.
- Derived vector writes must not change the optimistic-lock version or business
  ordering timestamp.

Level 2:

- The fake provider is deterministic test infrastructure, not a retrieval-quality
  implementation.
- Database CHECK constraints keep run timestamps/error fields consistent with
  lifecycle state and keep vector provenance all-null or all-present.
- Reconciliation creates missing runs with conflict-aware inserts and clears
  obsolete vector provenance without changing Experience business content.

## Knowledge Check

1. Why can Redis deliver a message twice without creating two durable runs?
2. Why does recovery increment `attempt`, and where is that attempt checked?
3. What deadlock could occur if Experience update locked the Experience before the
   run while worker completion locked them in the opposite order?
4. Why must embedding completion leave `version` and `updated_at` unchanged?
5. What additional evaluation is required before embeddings may replace lexical
   retrieval?
