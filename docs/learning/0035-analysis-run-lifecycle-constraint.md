# 0035 Analysis Run Lifecycle Constraint

## What Changed

PostgreSQL now enforces the relationship between an Analysis Run status and its
`started_at`, `finished_at`, and `error_code` fields. The SQLAlchemy metadata and
Alembic migration declare the same `ck_analysis_runs_lifecycle` constraint.

## Why It Exists

Repository methods already write valid transitions, but PostgreSQL is the system
of record. Scripts, repair operations, future code bugs, or direct SQL can bypass
the repository. The database must reject lifecycle states that the application
could not explain.

The valid persisted shapes are:

- `queued`: no start, finish, or error;
- `running`: started, but not finished and without an error;
- `succeeded`: started and finished, without an error;
- `failed`: started and finished, with an error;
- `cancelled`: finished; cancellation remains a reserved state with no public API.

## Failure Modes It Prevents

- A succeeded run without a completion timestamp.
- A failed run without a durable error code.
- A queued run that appears to have started.
- A running run that appears to have finished.
- A cancelled run without a finish timestamp.

## Migration Behavior

Creating a PostgreSQL CHECK validates all existing rows. If any row violates the
contract, the migration fails transactionally. It does not guess timestamps,
invent error codes, or rewrite data. The operator must investigate the source of
an invalid row before retrying.

Downgrade removes only this constraint. It does not change or delete Analysis Run
data.

## How It Was Verified

- The pre-migration read-only audit found 20 Analysis Runs and zero violations.
- The existing database upgraded, downgraded, and re-upgraded successfully.
- A temporary empty database upgraded from base through the new head.
- PostgreSQL rejected an invalid succeeded state while the normal fake-worker
  lifecycle still completed.
- Offline tests, strict typing, linting, and import-boundary checks passed.

## What You Must Understand

Level 1: lifecycle correctness is a persisted invariant, not merely a repository
convention. PostgreSQL remains authoritative even when application code has a bug.

Level 2: adding a CHECK to a populated table scans existing rows. A safe migration
therefore needs a preflight query and must fail rather than silently repair data.

## Knowledge Check

1. Why should the migration fail instead of filling in a missing `finished_at`?
2. Which fields distinguish `running`, `succeeded`, and `failed`?
3. Why is the same constraint declared in both SQLAlchemy metadata and Alembic?
4. What does downgrade remove, and what data does it preserve?
