# Dashboard Summary Test Record - 2026-09-13

Final pre-commit verification was rerun on 2026-09-15 after the authorization
filter review fix described below.

## Scope

This record verifies the Dashboard Summary and its Redis cache on top of commit
`ce22e26` plus the uncommitted Dashboard working tree. It is functional and query-
plan evidence, not a production latency, throughput, cache-hit-rate, or reliability
benchmark.

- Database: local PostgreSQL 16
- Cache: local Redis 7
- Cache TTL: 30 seconds
- Summary scope: current user's active Jobs and their Action Items
- LLM provider execution: none
- Groq requests: 0

## Offline Quality Gates

Commands:

```powershell
.\.venv\Scripts\python -m pytest -ra
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

Observed results:

```text
149 passed, 15 skipped
Success: no issues found in 83 source files
All checks passed!
Import contracts: 2 kept, 0 broken
```

The skipped default tests are explicitly gated infrastructure and live-provider
tests. No network or model request was enabled.

## PostgreSQL And Redis Integration

Commands:

```powershell
$env:CAREEROPS_RUN_INTEGRATION='1'
$env:CAREEROPS_REDIS_URL='redis://127.0.0.1:6379/0'
.\.venv\Scripts\python -m pytest tests/integration -ra
Remove-Item Env:CAREEROPS_RUN_INTEGRATION
Remove-Item Env:CAREEROPS_REDIS_URL
```

Observed result:

```text
13 passed, 2 skipped in 383.22s
```

The skipped tests require a separately enabled real Groq request and a continuously
running Dramatiq worker. The executed Dashboard integration path covered:

- fixed Job and Action Item status counts;
- cache fill, warm hit, and TTL inspection;
- per-user cache keys and cross-user authorization isolation, including a directly
  seeded cross-owner Action Item/Job association;
- post-commit invalidation after Job update, Action Item update, and Job archival;
- exclusion of archived Jobs and their retained tasks;
- three concurrent cold requests returning valid summaries;
- continued PostgreSQL operation when a real Redis client points to an unavailable
  endpoint.

The explicit `127.0.0.1` avoids this Windows host trying the unavailable IPv6
loopback address before Docker's IPv4 port mapping.

## Alembic Verification

Commands:

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\alembic check
```

Observed result: the database remained at the existing head and Alembic reported
`No new upgrade operations detected.` The Dashboard added no schema migration.

## Query Plan Inspection

`EXPLAIN (ANALYZE, BUFFERS)` was run for the single `UNION ALL` aggregate statement
against the local integration database. The selected user had two Job rows.

Observed plan outline:

```text
Append
  -> GroupAggregate (jobs.status)
       -> Seq Scan on jobs
  -> GroupAggregate (action_items.status)
       -> Hash Join
            -> Seq Scan on jobs
            -> Bitmap Heap Scan on action_items
                 -> Bitmap Index Scan on idx_action_items_user_job_updated
Planning Time: 0.323 ms
Execution Time: 0.107 ms
```

Interpretation: PostgreSQL preferred sequential scans for the tiny Jobs table and
used an existing user-prefixed Action Item index. This does not establish behavior
at production cardinality, but it provides no evidence that a new MVP index is
needed. The timing is diagnostic output for this local two-row case, not an endpoint
latency claim.

## Limitations

- No representative high-cardinality dataset was used.
- P50/P95 API latency and cache hit rate were not measured.
- Redis failover or recovery after an invalidation failure was not benchmarked.
- The accepted cache-aside race can expose a stale value for up to the 30-second TTL.
- No cache-stampede lock or generation key exists in this MVP.
- Docker control initially required sandbox elevation; this was an environment
  permission issue, not an application failure.
