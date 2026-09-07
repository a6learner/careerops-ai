# 0012 Worker-Backed Parse Execution

## What Changed

Parse submission now persists a `queued` run and sends its ID through
Dramatiq/Redis. An independent worker claims the run, parses an immutable input
snapshot through a fake adapter, validates the output, and commits either
`succeeded` requirements or a `failed` error code.

A recovery command can reset stale `running` rows and redispatch queued work
from PostgreSQL.

## Why It Exists

An API request should not wait for an unreliable model call. The worker boundary
keeps API latency predictable and lets worker concurrency, retries, and resource
usage evolve independently.

PostgreSQL stores the durable task state. Redis carries delivery hints; losing a
Redis message does not lose the parse run.

## Failure Modes It Prevents

- Slow model calls consuming API request workers.
- A Job edit causing the worker to parse text different from the submitted
  fingerprint.
- Duplicate Redis messages executing the parser twice.
- Partial requirement writes with a terminal success state.
- Redis downtime deleting accepted work.
- A crashed worker leaving a run permanently unrecoverable.
- Invalid parser spans being persisted as grounded output.

## How To Verify It

Run the local quality gates:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

Run PostgreSQL and Redis integration tests:

```powershell
docker compose up -d postgres redis
.\.venv\Scripts\alembic upgrade head
$env:CAREEROPS_RUN_INTEGRATION='1'
.\.venv\Scripts\python -m pytest tests/integration
Remove-Item Env:CAREEROPS_RUN_INTEGRATION
```

Run the worker and recovery command:

```powershell
.\.venv\Scripts\dramatiq careerops.workers.tasks --processes 1 --threads 4
.\.venv\Scripts\python -m careerops.workers.recovery
```

The recovery command prints requeue and dispatch counts. It exits nonzero when
any Redis dispatch fails so a scheduler does not record a partial recovery as a
successful run.

## What You Must Understand

Level 1: `202 Accepted` means durable work was accepted, not completed. The
client follows the parse-run resource until it reaches a terminal state.

Level 1: Database commit occurs before queue dispatch. If dispatch fails, the
queued row survives and the same idempotency key safely retries delivery.

Level 1: At-least-once queues may deliver duplicates. The PostgreSQL conditional
claim, not the absence of duplicate messages, guarantees one execution.

Level 1: The worker commits its claim before calling the parser so another
worker can observe `running`. Requirements and the success transition commit
together so partial results cannot appear successful.

Level 2: The adapter protocol keeps provider-specific SDKs and exceptions out of
the execution service. The fake adapter makes CI deterministic and free.

Level 2: Recovery changes stale `running` rows back to `queued`, increments the
attempt counter, and rebuilds delivery from PostgreSQL.

## Knowledge Check

1. Why does the queue message contain only `parse_run_id`?
2. Why must `input_text` be captured when the run is submitted?
3. What failure window exists between database commit and Redis dispatch?
4. Why are duplicate messages harmless only if claiming is atomic?
5. Why are requirements and the `succeeded` transition one transaction?
6. When would a transactional outbox become preferable to explicit recovery?
