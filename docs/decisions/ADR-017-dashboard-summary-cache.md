# ADR-017: Dashboard Summary With Disposable Redis Cache

## Status

Accepted

## Context

Jobs and Action Items now close the preparation-tracking loop, but the user has no
single read that summarizes active application and task progress. The summary is a
natural aggregation boundary and a small place to demonstrate caching without
making Redis authoritative.

The first version must avoid undefined semantics around latest Analysis Runs,
requirement coverage, recent activity, or archived work. Redis can fail or be
cleared without losing data.

## Decision

Expose `GET /api/v1/dashboard/summary` for the authenticated current user. The
response has fixed counters for every Job status and every Action Item status,
totals for both groups, and `generated_at`, which records when PostgreSQL produced
the cached snapshot.

Both groups use the same active-Job scope. Archived Jobs and their retained Action
Items are excluded from the Dashboard, while the Action Items API continues to
list and update those tasks. The Action Item aggregate filters ownership on both
the task and its joined Job so inconsistent cross-user rows cannot affect either
user's summary.

The repository executes one `UNION ALL` statement so Job and Action Item aggregates
share one PostgreSQL statement snapshot. Existing user/status indexes are eligible
for the filters; no new migration or index is added without query-plan evidence.

Use cache-aside with the user-scoped key:

```text
careerops:cache:dashboard-summary:v1:user:{user_uuid}
```

The value is compact UTF-8 JSON with a 30-second TTL. Cache read, write, decode, or
invalidation failure is fail-open: log a warning and use or preserve the PostgreSQL
result. Redis operations have a 200-millisecond socket/connect timeout.

Successful Job create, update, and soft delete invalidate after commit. Successful
Action Item creation invalidates only when a new row was created; idempotent replay
does not. Every successful Action Item update invalidates after commit. Parse,
Analysis, Evidence, and Experience writes do not invalidate because their values
are absent from this response.

The first version does not use a Redis lock or generation counter. Concurrent
cache misses may repeat the read-only SQL, and the classic miss-query/delete/set
race may leave a stale value for at most the TTL. This bounded staleness is accepted
for the single-user MVP.

## Alternatives Considered

- Include requirement or gap coverage: deferred because multiple Analysis Runs
  require an explicit latest-result policy before counts are meaningful.
- Include recent activity: rejected because the current schema has no durable event
  log and resource timestamps are not a complete activity model.
- Count archived Jobs or mix archived tasks into active counts: rejected because it
  gives the two groups different populations.
- Return an error when Redis is unavailable: rejected because PostgreSQL is the
  source of truth and the cache is an optimization.
- Add a Redis lock, generation key, or stale-while-revalidate: deferred until load
  or consistency requirements justify the extra states and failure modes.
- Add a summary table or new indexes: rejected without measured query-plan need.

## Consequences

The core user flow now has one global progress summary with stable empty states and
user isolation. Redis can be flushed and rebuilt from PostgreSQL. Successful writes
are never rolled back because cache invalidation failed.

The response may be stale for up to 30 seconds after an invalidation failure or a
cache-aside race. Concurrent cold reads may duplicate SQL. `generated_at` exposes
snapshot age but is not a strict read-your-writes guarantee.

The API now imports `redis` directly, so the Redis client is declared as a direct
runtime dependency instead of relying on `dramatiq[redis]` to install it transitively.

## Verification Or Evidence

- Unit tests cover hit, miss, JSON round-trip, malformed values, Redis failures,
  fixed zero states, post-commit invalidation, and idempotent replay.
- PostgreSQL/Redis integration covers authorization isolation, including a seeded
  cross-owner row, TTL, warm hits, Job and Action Item invalidation, archived
  scope, and concurrent cold reads.
- `EXPLAIN (ANALYZE, BUFFERS)` is saved in the Dashboard test record. The small
  local dataset does not justify a new index or a production latency claim.
- Default pytest, strict mypy, Ruff, import-linter, Alembic check, and the full
  infrastructure integration suite remain required gates.

## Revisit If

- Requirement coverage or per-Job summaries become explicit product requirements.
- Measured load shows cache stampede or aggregation cost is material.
- Product behavior requires strict read-your-writes rather than bounded staleness.
- A representative dataset shows that existing indexes do not support the query.
