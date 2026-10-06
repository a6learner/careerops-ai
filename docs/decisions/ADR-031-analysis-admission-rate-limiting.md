# ADR-031: Analysis Admission Rate Limiting

## Status

Accepted

## Context

Analysis submission is idempotent and durable, but different idempotency keys can
create unbounded work for one user. P1-5 added an explicitly authorized real
matcher path, so API admission must protect queue capacity and provider cost
before a new Analysis Run is persisted or dispatched.

The limiter must preserve the existing PostgreSQL idempotency contract. Replaying
an accepted request is not new work and must remain available even when the user
has exhausted the current window. Redis remains disposable and cannot become the
source of truth for Analysis Run state.

## Decision

Apply a per-user sliding-window limit only to creation of new Analysis Runs. The
default is five new runs per 3,600 seconds. Both values are configurable with
bounded settings.

Use one versioned Redis sorted-set key per authenticated user. An atomic Lua
script uses Redis server time, removes expired reservations, checks the current
count, and either records a unique reservation token or returns the number of
seconds until the oldest reservation leaves the window.

Submission keeps this order:

1. Validate ownership, Parse Run readiness, and the current Experience input.
2. Return a matching idempotency replay before consulting the limiter.
3. Reserve one Redis slot.
4. Create or converge on the PostgreSQL queued run.
5. Release the request's reservation if another concurrent request already
   created the same idempotency key.
6. Commit a newly created run, then dispatch it.

An admitted durable run keeps its reservation even when Redis dispatch fails,
because PostgreSQL already contains accepted work and recovery may redispatch it.
An exception before the repository returns a creation result releases the
reservation on a best-effort basis. A process crash in that narrow interval may
leave a conservative reservation until the window expires; no cross-store
transaction is introduced.

Limit rejection returns HTTP 429, error code `ANALYSIS_RATE_LIMITED`, a
`Retry-After` header, and `details.retry_after_seconds`. Redis reservation failure
is fail-closed with HTTP 503 and `DEPENDENCY_UNAVAILABLE`. Release failure is
logged without user content and expires naturally.

Redis deletion resets the admission window but never changes a PostgreSQL run.
The limiter is cost protection, not a billing ledger or a durable quota system.

Queued idempotency replay still redispatches the existing run so a prior broker
failure can be repaired. Replays do not create new durable work or consume another
provider slot, but an abusive client can therefore create duplicate broker
messages. Conditional worker claiming prevents duplicate model execution; P1-6
does not claim complete broker-capacity protection. A short Redis redispatch
suppression key may be added later if measured pressure justifies it, without a
database field or transactional outbox.

## Alternatives Considered

- Count every POST, including replay: rejected because retrying an accepted
  idempotent request is not new work and may be required after dispatch failure.
- Rate-limit in the worker: rejected because the API would already have persisted
  and queued excess work.
- Store quota state in PostgreSQL: stronger durability, but adds schema and row
  contention for a short-lived admission concern.
- Fail open when Redis is unavailable: rejected because the limiter exists to
  protect an explicitly costly external-effect path.
- Use an in-process counter: rejected because multiple API processes would enforce
  different limits and restarts would silently reset only one process.
- Add a distributed transaction across PostgreSQL and Redis: rejected as
  disproportionate for an expiring MVP admission window.
- Suppress repeated replay dispatch now: deferred because replay currently repairs
  broker publication failure and no measured broker-capacity problem justifies a
  second Redis lifecycle in this slice.

## Consequences

New work has an atomic per-user admission bound across API processes. Idempotency
replay, PostgreSQL task durability, worker attempt fencing, matcher identity, and
result transactions remain unchanged.

Redis becomes an availability dependency for new Analysis Run creation, but not
for reads, replays, recovery, or existing durable work. Clearing Redis can permit
up to a fresh window of work, which is an explicit limitation of disposable
admission state.

Repeated replay can still consume broker and worker-claim throughput even though
it cannot create duplicate rows or duplicate provider execution.

## Verification Or Evidence

Unit and API tests cover key scope, settings, allowed and rejected Lua results,
fail-closed reserve behavior, best-effort release, 429 headers and body, replay
bypass, concurrent-idempotency loser release, and no create or dispatch after
rejection. The exact Lua script is also exercised against the project Redis
container for atomic limit and user-isolation behavior.

PostgreSQL Analysis integration remains fake-matcher-only. No provider call,
holdout access, migration, or retrieval change is part of this decision.

## Revisit If

- The product needs paid plans or durable quota accounting.
- Multiple API regions require a different Redis topology.
- Provider-wide TPM coordination must span users and worker processes.
- Measured usage justifies separate limits for fake and real matcher pipelines.
