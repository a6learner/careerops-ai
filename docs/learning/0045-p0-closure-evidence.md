# 0045 P0 Closure Evidence And Safe Boundaries

## What Changed

P1-11 adds a dependency-light read benchmark, fresh-database migration CI job,
one-step rollback drill, timed fake-provider browser demo, explicit refresh-token
deferral, and a final P0 evidence/limitation matrix.

## Why It Exists

Feature completion and delivery evidence are different. P0 closure makes each
claim traceable to a test or saved artifact and turns unimplemented or unmeasured
behavior into an explicit limitation instead of an implied capability.

## Failure Modes It Prevents

- invented or irreproducible performance numbers;
- destructive downgrade of a developer database;
- late container-start failures when a port is already published by Docker;
- erasing a developer's pre-existing `CAREEROPS_*` shell configuration after a drill;
- a migration chain that works only on an already-evolved database;
- accidental real-provider calls during a demo;
- advertising an unimplemented refresh endpoint;
- treating local synthetic success as production availability.

## How To Verify It

- Run the focused percentile unit tests.
- Run the isolated read benchmark and inspect its raw JSON samples and plans.
- Run the rollback harness and confirm exact cleanup.
- Verify occupied host ports fail before build/resource creation and that prior
  environment-variable values are restored.
- Execute the CI migration commands against a fresh pgvector database.
- Run the acceptance harness with `-DemoRehearsal` and confirm the browser phase
  is between 180 and 300 seconds.

## What You Must Understand

Level 1: A percentile is computed from measured samples, not an average or a
target. An index-plan change is not automatically a latency improvement. A
rollback claim is bounded to a specific revision and data shape. Refresh tokens
create a session-lifecycle security contract, not merely another JWT endpoint.

Level 2: The benchmark uses nearest-rank percentiles, synthetic database seeds,
and exact cleanup. The CI migration job starts a blank pgvector service and
checks both `upgrade head` and model/migration drift. The rollback harness verifies
constraint removal and restoration around one safe boundary.

## Knowledge Check

1. Why can the indexed plan be correct even when one 5,000-row `EXPLAIN ANALYZE`
   is not faster than the sequential scan?
2. Why is the rollback claim limited to `202610060001 <-> 202609190001`?
3. What makes a fresh-database CI migration check different from `alembic check`?
4. Which security decisions must be made before adding refresh tokens?
5. Why does a 4-minute fake-provider browser rehearsal not prove production
   reliability or model quality?
