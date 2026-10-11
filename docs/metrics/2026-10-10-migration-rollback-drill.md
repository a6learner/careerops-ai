# Migration Rollback Drill — 2026-10-10

## Scope

This is local synthetic evidence for the currently supported rollback boundary.
It is not evidence that every historical migration is reversible and it did not
touch the development database.

- Run ID: `20261010b`
- Compose project: `careerops-p111-rollback-20261010b`
- Database: isolated PostgreSQL 16 with pgvector
- Boundary: `202610060001 <-> 202609190001`
- Providers: not started; no model call was possible

## Result

| Check | Result |
|---|---|
| Fresh database `alembic upgrade head` | passed |
| `alembic check` after fresh upgrade | passed |
| Seed valid User, Job, Parse Run, and Analysis Run | passed |
| Downgrade head to `202609190001` | passed |
| Lifecycle constraint removed at the lower revision | passed |
| Seed data preserved after downgrade | passed |
| Re-upgrade to head | passed |
| Lifecycle constraint restored | passed |
| Seed data preserved after re-upgrade | passed |
| Invalid succeeded Analysis Run rejected after re-upgrade | passed |
| Exact containers, network, and volume cleanup | passed |

The expected PostgreSQL CHECK-constraint error from the invalid final insert is
positive evidence that `ck_analysis_runs_lifecycle` was restored.

## Supported Boundary

The supported rollback drill is one revision only: head `202610060001` down to
`202609190001`, followed by re-upgrade to head. This migration removes and
recreates one Analysis Run lifecycle CHECK constraint; it does not drop tables or
business rows. Older, multi-step, or destructive downgrades are not covered.

## Reproduction

```powershell
.\scripts\local_migration_rollback_drill.ps1 -RunId <unique-run-id>
```

The harness refuses to reuse an existing project or occupied port, runs only
against its own disposable Compose database, and removes only resources carrying
its exact Compose project label.

## Limitations

- This was a local Docker drill, not a production rollback.
- It proves the latest one-step boundary only.
- A production rollback still requires a backup, a deployment-specific decision,
  and validation against the actual production data shape.
