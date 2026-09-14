# ADR-016: Job-Scoped Action Items With Gap Provenance

## Status

Accepted

## Context

Analysis Runs now expose evidence-backed matches and explicit gaps, but the user
cannot yet turn preparation needs into tracked work. The first task slice must
support manual tasks and tasks created from `partial`, `missing`, or
`insufficient_evidence` results without introducing Dashboard caching or another
AI dependency.

Tasks must survive Job soft deletion. Repeated client submissions also need a
durable identity, while the same gap must remain eligible for multiple distinct
tasks.

## Decision

Add a user-owned, Job-scoped `action_items` resource with only `title`,
`todo | doing | done` status, optimistic-lock version, timestamps, and an optional
`source_evidence_match_id`.

- Every task requires an active owned Job at creation time. There are no global
  tasks in this version.
- Manual tasks have no evidence-match source.
- Gap-derived tasks reference an Evidence Match from a succeeded Analysis Run for
  the same user and Job. Only `partial`, `missing`, and `insufficient_evidence`
  are actionable. `matched` is rejected.
- The client always supplies the title. The backend does not generate task text or
  call a model.
- Job soft deletion does not delete or hide tasks. Responses derive
  `job_is_archived` from `jobs.deleted_at`.
- Existing tasks remain editable after Job archival, but new tasks cannot be
  created for an archived Job.
- Status transitions are intentionally reversible; for example, a completed task
  may return to `doing`.

Expose:

```text
POST  /api/v1/action-items
GET   /api/v1/action-items
PATCH /api/v1/action-items/{action_item_id}
```

POST requires `Idempotency-Key`. The key is unique per user and is bound to a
fingerprint of Job, title, and optional source. A same-key replay returns the
existing task; different payload returns `409 IDEMPOTENCY_KEY_CONFLICT`. There is
no uniqueness constraint on the source Evidence Match, so different keys can
create multiple tasks from one gap.

PATCH accepts title and/or status and requires `If-Match`. List queries use a
stable `(updated_at, id)` cursor and optional Job and status filters. This version
has no delete endpoint.

Separate user-and-order, user/status/order, and user/Job/order indexes match the
default list and both supported filtered list shapes. This accepts modest write
amplification so the primary task-list reads do not require an avoidable sort.

Database constraints enforce status membership, non-blank bounded titles,
positive versions, valid fingerprint/key lengths, foreign keys, and unique
per-user idempotency keys. Application validation enforces cross-table ownership,
same-Job provenance, succeeded Analysis Run state, and actionable verdicts.

## Alternatives Considered

- Global tasks without a Job: rejected because they are outside the current
  job-preparation loop and complicate Dashboard semantics.
- Store only a requirement ID: rejected because it loses the exact Analysis Run
  verdict that caused the task.
- Make the source Evidence Match unique: rejected because one gap may require
  multiple independent preparation actions.
- Generate titles from requirements or an LLM: rejected because explicit user
  titles are simpler, editable, deterministic, and need no provider.
- Hide or freeze tasks when a Job is archived: rejected because archival should
  not destroy the user's remaining preparation work.
- Add Dashboard invalidation in the same change: deferred so task persistence and
  authorization can be verified independently from Redis caching.

## Consequences

Tasks retain durable provenance without turning evidence results into mutable task
state. PostgreSQL handles concurrent create and update races through unique keys
and conditional version updates.

The API performs joins to derive the archived flag and validate source ownership.
No cached Dashboard aggregate exists yet, so this slice has no Redis invalidation
behavior. That becomes the next milestone.

## Verification Or Evidence

- Schema and service tests cover title validation, actionable verdicts,
  idempotency conflict detection, cursor encoding, and optimistic locking.
- PostgreSQL integration covers same-key concurrent creation, same-gap multiple
  tasks, cross-user hiding, cross-Job source rejection, archived Job retention,
  post-archive updates, and database constraints.
- Alembic upgrade, downgrade, and re-upgrade are required.
- Default pytest, `mypy --strict`, Ruff, and import-linter remain required gates.

No model, retrieval-quality, latency, throughput, or cache metric is part of this
decision.

## Revisit If

- Users need tasks that are not attached to a Job.
- Task collaboration, deletion, due dates, priority, descriptions, or richer
  workflow states become an explicit product requirement.
- Historical display needs a copied requirement snapshot rather than immutable
  Evidence Match provenance.
