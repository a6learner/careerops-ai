# 0018 Dashboard Aggregation And Cache

## What Changed

The backend now exposes one authenticated Dashboard Summary containing fixed Job
and Action Item status counts. PostgreSQL computes the authoritative snapshot in a
single statement. Redis caches the typed JSON response for 30 seconds, and Job or
Action Item writes invalidate the current user's key after committing.

Archived Jobs and their tasks are excluded from Dashboard counts. They remain
available through the Action Items API.

## Why It Exists

The Dashboard closes the MVP core loop without making clients issue many filtered
list requests and count pages themselves. It also provides a narrow, testable place
to practice cache-aside, invalidation, bounded staleness, dependency failure, and
query-plan inspection.

## Failure Modes It Prevents

- One user's cached counts being returned to another user.
- A cross-owner Action Item/Job association affecting either user's aggregate.
- Missing status fields forcing clients to guess whether zero means absent.
- Redis loss becoming application data loss.
- A Redis outage taking down an otherwise healthy PostgreSQL read.
- Cache invalidation running before a database commit that later fails.
- An idempotent Action Item replay being mistaken for a new write.
- Archived Jobs disappearing from storage or mixing into active progress counts.
- Two separate aggregate statements observing different database snapshots.

The MVP knowingly accepts duplicate SQL on concurrent cache misses and up to 30
seconds of stale data after an invalidation failure or cache-aside race.

## How To Verify It

Run offline checks:

```powershell
.\.venv\Scripts\python -m pytest -ra
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

Run PostgreSQL and Redis integration tests:

```powershell
docker compose up -d postgres redis
.\.venv\Scripts\alembic upgrade head
$env:CAREEROPS_RUN_INTEGRATION='1'
$env:CAREEROPS_REDIS_URL='redis://127.0.0.1:6379/0'
.\.venv\Scripts\python -m pytest tests/integration -ra
Remove-Item Env:CAREEROPS_RUN_INTEGRATION
Remove-Item Env:CAREEROPS_REDIS_URL
```

No live-provider flag is required. The Dashboard does not call a worker or model.

## What You Must Understand

Level 1:

- Cache-aside means the service reads Redis first, computes from PostgreSQL on a
  miss, and then fills Redis. PostgreSQL remains authoritative.
- Cache invalidation occurs after commit because deleting first can expose stale
  data if the transaction then fails or rolls back.
- Post-commit deletion still does not provide strict consistency. A concurrent
  miss may write an older snapshot after deletion, so TTL bounds the risk.
- One SQL statement gives both aggregate groups one statement snapshot under
  PostgreSQL's default `READ COMMITTED` isolation.
- Fail-open caching preserves availability but allows temporary staleness after an
  invalidation failure.

Level 2:

- The cache key includes schema version and user UUID to support response evolution
  and authorization isolation.
- Cache JSON is validated before becoming a domain object; malformed data is a miss.
- Service protocols keep Redis out of business tests and preserve API -> service ->
  repository dependency direction.
- The Action Item aggregate checks both task ownership and joined Job ownership;
  API validation alone is not a substitute for read-side authorization filtering.
- Query plans depend on real cardinality. A sequential scan on a tiny table can be
  cheaper than an index scan and is not automatically a defect.

## Knowledge Check

1. Why must Redis never be the only copy of Dashboard counts?
2. Why is invalidation performed after database commit?
3. What race can still produce a stale value after write-side deletion?
4. Why are archived Job tasks excluded from Dashboard but retained in Action Items?
5. What does `generated_at` mean on a cache hit?
6. When would a generation key or distributed lock become justified?
7. Why should a test not require PostgreSQL to choose an index on a tiny fixture?
