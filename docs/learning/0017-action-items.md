# 0017 Action Items

## What Changed

The backend now supports the first task-tracking slice:

- manual Job-scoped Action Items;
- conversion of `partial`, `missing`, and `insufficient_evidence` results into
  Action Items;
- idempotent creation with same-gap multiple-task support;
- status and title updates protected by `If-Match`;
- cursor pagination with Job and status filters;
- retained tasks and an explicit `job_is_archived` flag after Job soft deletion.

The slice does not include Dashboard aggregation, Redis caching, deletion, due
dates, priority, descriptions, or model-generated suggestions.

## Why It Exists

An analysis is useful only if the user can turn a gap into concrete work. Action
Items close that part of the core loop while preserving the exact evidence result
that motivated a task.

Task state is ordinary synchronous PostgreSQL data. It does not need a worker or
LLM boundary. Keeping it separate from Dashboard caching lets persistence and
authorization be verified before introducing cache invalidation.

## Failure Modes It Prevents

- A double click creates duplicate tasks for one logical request.
- Reusing an idempotency key with different content silently returns the wrong
  task.
- One user creates or updates a task through another user's Job or Evidence Match.
- A gap from one Job is attached to a task for another Job.
- A fully matched requirement is incorrectly presented as a gap task.
- Two clients overwrite each other's title or status updates.
- Archiving a Job hides or breaks its existing tasks.
- An unbounded list becomes unstable while tasks are updated.

## How To Verify It

Run offline checks:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

Run PostgreSQL integration tests:

```powershell
.\.venv\Scripts\alembic upgrade head
$env:CAREEROPS_RUN_INTEGRATION='1'
.\.venv\Scripts\python -m pytest tests/integration/test_action_items_postgres.py
Remove-Item Env:CAREEROPS_RUN_INTEGRATION
```

Verify migration reversibility:

```powershell
.\.venv\Scripts\alembic downgrade 202609120001
.\.venv\Scripts\alembic upgrade head
```

## What You Must Understand

Level 1:

- Idempotency identifies one create request; it does not mean one task per gap.
  Different keys intentionally create different tasks from the same Evidence Match.
- The unique database index closes the concurrent check-then-insert race.
- Optimistic locking prevents lost updates without holding a long transaction.
- Soft deletion is a display state for the parent Job, not a cascade event. The
  task remains queryable and editable.
- Authorization must validate both the task owner and the ownership/provenance of
  any referenced Evidence Match.

Level 2:

- `request_fingerprint` binds an idempotency key to normalized request content.
- The repository joins Jobs without filtering `deleted_at`, allowing it to derive
  `job_is_archived`.
- Conditional `UPDATE ... WHERE version = expected_version` is the final write-race
  guard after the service's user-friendly version check.
- The cursor uses both timestamp and UUID so equal timestamps have a stable order.
- The default, status-filtered, and Job-filtered list shapes have matching index
  prefixes; an index beginning with status or Job alone would not cover the
  unfiltered user list ordering.

## Knowledge Check

1. Why is the idempotency unique index on `(user_id, idempotency_key)` rather than
   on `source_evidence_match_id`?
2. How can two tasks legitimately point to the same gap?
3. Why does source validation join through the Analysis Run instead of trusting a
   client-supplied Job ID?
4. What race remains if the service checks `version` but the repository update does
   not include it in the SQL predicate?
5. Why may an archived Job's task still be updated, while creating a new task for
   that Job is rejected?
6. What write paths must invalidate the Dashboard cache in the next milestone?
