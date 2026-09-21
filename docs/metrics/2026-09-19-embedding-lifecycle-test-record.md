# Experience Embedding Lifecycle Test Record - 2026-09-19

## Scope

This record verifies the P1-1 Experience Embedding Lifecycle developed on top of
commit `af86021`. It is functional and concurrency evidence, not a
retrieval-quality, latency, throughput, reliability, or cost benchmark.

- Database: local PostgreSQL 16 with pgvector
- Queue dependency: local Redis 7
- Embedding provider: deterministic `local-fake-embedding-1536`
- Embedding dimensions: 1536
- Pgvector retrieval or ANN index: not implemented
- Real embedding or Groq requests: 0

## Offline Quality Gates

Commands:

```powershell
.\.venv\Scripts\python -m pytest -ra
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
.\.venv\Scripts\python -m pip check
```

Observed results:

```text
161 passed, 19 skipped
Success: no issues found in 89 source files
All checks passed!
Import contracts: 2 kept, 0 broken
No broken requirements found.
```

The default suite made no network or real-provider request.

## PostgreSQL And Redis Integration

Command:

```powershell
$env:CAREEROPS_RUN_INTEGRATION='1'
$env:CAREEROPS_REDIS_URL='redis://127.0.0.1:6379/0'
.\.venv\Scripts\python -m pytest tests/integration -ra
```

Observed result:

```text
17 passed, 2 skipped in 490.76s
```

The skipped cases require an explicitly enabled real Groq request and a
continuously running worker. The executed embedding cases covered:

- version-bound queued work after Experience create and update;
- 1536-dimensional pgvector write and read;
- old work becoming superseded after an Experience edit;
- stale completion being unable to overwrite current content;
- soft deletion clearing the current vector without queuing new work;
- a mismatched user ID being unable to supersede another user's active run;
- concurrent duplicate claims allowing one winner;
- recovery incrementing `attempt` and fencing the old worker;
- reconciliation backfilling an existing Experience exactly once;
- Redis messages containing only the embedding run ID;
- the existing Auth, Experiences, Jobs, Parse Run, Analysis Run, Action Items,
  evidence-integrity, and Dashboard/Redis integration cases.

The integration duration is test-suite runtime, not an endpoint or worker latency
claim.

After the authorization-focused repository review, the embedding lifecycle and
Redis dispatcher integration files were rerun together:

```text
6 passed in 127.97s
```

## Migration And Worker Verification

Migration `202609190001` was upgraded, downgraded to `202609120002`, and upgraded
again. The final revision is `202609190001 (head)`, and `alembic check` reported:

```text
No new upgrade operations detected.
```

The embedding actor import reported:

```text
execute_embedding_run
```

## Limitations

- The fake vector has no semantic retrieval-quality meaning.
- No Recall@K, MRR, ranking comparison, P50/P95 latency, throughput, provider
  reliability, token usage, or cost was measured.
- Analysis Runs still use deterministic lexical/skill Top-5 retrieval.
- Failed fake-provider runs are terminal; real-provider retry classification is
  deferred.
- Docker CLI access from the sandbox reported a local user-config/API permission
  warning, but the configured PostgreSQL and Redis endpoints were reachable and
  the integration suite completed.
