# ADR-011: Worker-Backed Parse Execution

## Status

Accepted

## Context

ADR-010 established parse runs, job requirements, idempotent submission, and a
deterministic parser, but the API still performed parsing before returning. That
temporary behavior did not satisfy the architectural requirement that unreliable
model work execute outside the API process.

Moving execution to a worker introduces two failure boundaries: PostgreSQL may
commit before Redis accepts the message, and Redis may deliver the same message
more than once. A Job may also change between submission and worker execution.

## Decision

`POST /api/v1/jobs/{job_id}/parse-runs` creates or reuses a `queued` parse run,
commits it to PostgreSQL, and then dispatches only the `parse_run_id` through
Dramatiq backed by Redis. The API never calls a requirement parser.

Each parse run stores an immutable `input_text` snapshot. The worker parses that
snapshot instead of the current Job row, so its source spans and input
fingerprint describe the exact submitted input.

The worker uses a `RequirementParser` protocol. CI and local tests use a
deterministic fake adapter with no network access or cost. ADR-012 adds Groq as
the first real implementation without changing the execution service contract.

Worker state transitions use conditional PostgreSQL updates:

```text
queued -> running -> succeeded
                  -> failed
```

Only a worker that atomically changes `queued` to `running` executes the parser.
Duplicate messages therefore become no-ops. Requirements and the `succeeded`
transition commit in one transaction. Provider or validation failures persist a
stable error code with the `failed` transition.

Dispatch happens after the queued row commits. If Redis is unavailable, the API
returns `503 DEPENDENCY_UNAVAILABLE`; retrying with the same idempotency key
redispatches the same queued run. A recovery command resets stale `running` rows
to `queued`, increments `attempt`, and redispatches queued rows from PostgreSQL.
This keeps PostgreSQL as the source of truth and Redis rebuildable.

Dramatiq transport retries are disabled for this first worker slice. Duplicate
delivery safety and explicit PostgreSQL recovery are implemented before adding
bounded provider retry policy.

## Alternatives Considered

- Parse in the API and return a completed run: rejected because model latency
  and failures would affect API request latency and violate the worker boundary.
- Put the full JD in Redis: rejected because Redis is disposable and the queue
  message should contain only a stable database identifier.
- Read the latest Job text in the worker: rejected because edits after
  submission would make the stored fingerprint and source spans incorrect.
- Use an in-process FastAPI background task: rejected because work would be lost
  on process restart and could not scale independently.
- Add a transactional outbox immediately: deferred because idempotent redispatch
  plus PostgreSQL recovery handles the current single-user MVP with less
  machinery. Revisit if observed message-loss guarantees require it.

## Consequences

The POST response now normally contains a `queued` run with no requirements.
Clients poll the existing GET endpoint to observe terminal state.

Duplicate queue messages are expected and safe. Redis failure cannot delete the
run because the database commit occurs first. A failed dispatch may leave a
queued row until the client retries or recovery runs.

The worker is an independent process but remains part of the monolithic backend
codebase. No microservice boundary or separate system of record is introduced.

## Verification Or Evidence

- Unit tests cover queued submission, redispatch, dispatch failure, parser
  success, parser failure, invalid output, duplicate execution, and recovery.
- PostgreSQL integration tests cover concurrent claims, terminal state writes,
  failed output validation, stale-run recovery, and immutable input snapshots.
- Redis integration verifies that the dispatcher enqueues only `parse_run_id`.
- Alembic upgrade and downgrade cover the input snapshot and lifecycle check.
- `mypy --strict`, Ruff, import-linter, and pytest are required to pass.

No parser-quality, throughput, or latency metric is claimed.

## Revisit If

Revisit when adding bounded provider retries, scheduling automatic recovery,
introducing a real LLM adapter, or when deployment evidence shows that a
transactional outbox is necessary.
