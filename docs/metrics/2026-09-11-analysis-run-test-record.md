# Analysis Run Test Record - 2026-09-11

Final pre-commit verification was repeated on 2026-09-12 after clarifying that
idempotency is scoped to the client-provided key rather than the input fingerprint.

## Scope

This is verification evidence for the deterministic Analysis Run end-to-end
workflow. It is not a retrieval-quality, latency, throughput, reliability, or cost
benchmark.

- Git base: `b72af72` plus the uncommitted Analysis Run working tree
- Database: local PostgreSQL 16 with pgvector extension available but unused here
- Queue dependency: local Redis 7
- Evidence matcher: `local-fake-evidence-matcher`
- Groq requests: 0

## Offline Quality Gates

Commands:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

Observed results:

```text
120 passed, 11 skipped
Success: no issues found in 71 source files
All checks passed!
Import contracts: 2 kept, 0 broken
```

The skipped default tests are explicitly gated integration tests. The default suite
made no network or real-provider request.

## PostgreSQL And Redis Integration

Command:

```powershell
$env:CAREEROPS_RUN_INTEGRATION='1'
.\.venv\Scripts\python -m pytest tests/integration -q
Remove-Item Env:CAREEROPS_RUN_INTEGRATION
```

Observed result:

```text
9 passed, 2 skipped
```

The two skipped cases require separate opt-in flags for the live Groq compatibility
test and the older E2E test that expects a continuously running Dramatiq worker.
Neither flag was enabled.

The executed integration cases covered:

- Analysis API submission, idempotent replay, fake-worker execution, and result query;
- cross-user resource hiding;
- one-verdict-per-requirement database enforcement;
- concurrent submissions with the same idempotency key converging on one Analysis
  Run, while a different key creates a distinct run;
- stale running Analysis Runs returning to queued with an incremented attempt;
- Redis messages containing only the Analysis Run ID;
- the existing evidence transaction rollback test.

## Migration Verification

Commands:

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\alembic downgrade 202609110001
.\.venv\Scripts\alembic upgrade head
```

Observed result: upgrade, downgrade, and re-upgrade completed successfully for
revision `202609120001`.

## Worker Image Verification

Commands:

```powershell
docker compose build worker
docker compose run --rm --no-deps worker python -c `
  "from careerops.workers.tasks import execute_analysis_run; print(execute_analysis_run.actor_name)"
```

Observed result:

```text
Image careerops-ai-worker Built
execute_analysis_run
```

## Limitations

- Retrieval relevance was not evaluated against labeled evidence matches.
- No embeddings or pgvector query were executed.
- No live evidence-matching provider exists in this slice.
- P50/P95 latency, throughput, retry rate, and task success rate were not measured.
- Container import verifies actor loading, not a continuously running worker process.
