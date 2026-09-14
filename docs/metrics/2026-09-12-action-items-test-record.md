# Action Items Test Record - 2026-09-12

## Scope

This record verifies the P0-6 Action Items slice on top of commit `a3689c4`.
It is functional test evidence, not a latency, throughput, cache, or reliability
benchmark.

- Database: local PostgreSQL 16
- Action Item execution: synchronous API/service/repository path
- Evidence source: persisted deterministic Analysis Run fixtures
- Dashboard or Redis cache changes: none
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
139 passed, 13 skipped
Success: no issues found in 76 source files
All checks passed!
Import contracts: 2 kept, 0 broken
```

The 13 default skips are opt-in infrastructure and live-provider tests. The
default suite made no network or model request.

## PostgreSQL Integration

Command:

```powershell
$env:CAREEROPS_RUN_INTEGRATION='1'
.\.venv\Scripts\python -m pytest tests/integration -ra
Remove-Item Env:CAREEROPS_RUN_INTEGRATION
```

Observed result:

```text
11 passed, 2 skipped in 329.88s
```

The two skips require a separate opt-in live Groq request and a continuously
running Dramatiq worker. Neither was needed by Action Items.

The executed tests covered:

- manual Action Item creation and `todo` default state;
- `partial`, `missing`, and `insufficient_evidence` source acceptance;
- `matched` source rejection;
- cross-Job source rejection and cross-user task hiding;
- same-key replay and conflicting-payload rejection;
- three concurrent same-key requests converging on one row;
- multiple tasks from one gap when different keys are used;
- Job/status filters and cursor pagination;
- `If-Match` requirements, stale-version conflicts, and title/status updates;
- task retention and continued updates after Job soft deletion;
- rejection of new tasks for archived Jobs;
- database rejection of invalid status, blank title, non-positive version, and
  duplicate per-user idempotency key;
- the existing Auth, Experiences, Jobs, Parse Run, Analysis Run, evidence
  integrity, and Redis integration cases.

## Migration Verification

Commands:

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\alembic downgrade 202609120001
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\alembic current
```

Observed result: upgrade, downgrade, and re-upgrade completed successfully;
current revision is `202609120002 (head)`.

An additional `alembic check` initially exposed a pre-existing metadata mismatch
from commit `a3689c4`: the `experiences` model omitted the `DESC` direction used by
migration `202609030001`. The model declaration was aligned with the existing
migration without changing database semantics. The final schema check reports no
new upgrade operations.

## Limitations

- Dashboard aggregation, Redis caching, and write-side invalidation are not part
  of this slice.
- No Action Item delete endpoint exists.
- No priority, due date, description, or global task behavior exists.
- P50/P95 latency, throughput, cache hit rate, and production task success rate
  were not measured.
- The integration duration is test-run timing, not an endpoint performance claim.
