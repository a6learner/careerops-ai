# Analysis Run Lifecycle Constraint Test Record

## Scope

This record covers the deployment-preparation hardening that adds
`ck_analysis_runs_lifecycle`. It does not add fields, indexes, APIs, cancellation
behavior, data repair, or new infrastructure.

## Preflight

The local PostgreSQL database contained 20 Analysis Runs, all succeeded. A
read-only query evaluated the proposed predicate against every row and found zero
violations. The previous Alembic head was `202609190001`, and no Analysis Run
lifecycle constraint existed.

## Behavior Verified

- queued, running, succeeded, failed, and cancelled states have explicit persisted
  timestamp and error-code shapes;
- SQLAlchemy metadata and the migration use the same named constraint;
- PostgreSQL rejects an invalid succeeded run with missing lifecycle timestamps;
- the normal fake-worker path can still claim and complete a queued run;
- migration failure would leave invalid existing data unchanged rather than
  manufacturing a repair.

## Migration Verification

- Existing populated database: upgrade to `202610060001` passed.
- Existing populated database: downgrade to `202609190001` passed.
- Existing populated database: re-upgrade to `202610060001` passed.
- Temporary empty database: base-to-head upgrade passed and the named constraint
  was present at head.
- The temporary verification database was deleted after inspection.

## Quality Gates

- Default offline suite: 314 passed and 21 infrastructure-gated tests skipped.
- Both PostgreSQL Analysis Run integration tests passed, including direct
  constraint rejection, fake-worker completion, recovery, and attempt fencing.
- `mypy --strict` passed across 120 source files.
- Ruff and both import-boundary contracts passed.
- No real provider request was authorized or made.
