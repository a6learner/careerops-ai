# 0033 Analysis Admission Rate Limiting

## What Changed

Creating a new Analysis Run now reserves one per-user Redis sliding-window slot
before PostgreSQL persists the queued run. The default is five new runs per hour.
An idempotent replay bypasses the limiter, while a concurrent request that loses
the same-key database race releases its own reservation.

## Why It Exists

Idempotency prevents accidental duplicate work for one request identity; it does
not stop a client from generating unlimited distinct identities. Admission
control bounds accepted work before it can consume queue capacity or provider
quota.

## Failure Modes It Prevents

- One user creating an unbounded number of Analysis Runs with different keys.
- Two API processes independently accepting more work than the shared limit.
- A full window blocking recovery of an already accepted idempotent request.
- A rejected request leaving a PostgreSQL row or queue message.
- A same-key concurrency loser permanently consuming a second quota slot.
- Redis failure silently disabling cost protection.
- Host clock skew producing different windows across API processes.

## Lifecycle And Recovery

The Lua script uses Redis server time and performs expiry cleanup, count, and
reservation atomically. PostgreSQL remains authoritative for work state.

The reservation is retained after the new run commits, including when dispatch
fails, because recovery can redispatch that durable run. Failures before a
creation result and known same-key losers release their reservation. Release is
best effort; a missed release expires with the window.

Deleting Redis resets the current window but cannot delete or change an Analysis
Run. The limiter is therefore disposable operational state, not a durable usage
ledger.

Queued replay still republishes the existing run to preserve recovery after a
dispatch failure. Conditional claiming makes duplicate messages harmless to model
execution, but they can consume broker and worker throughput. This stage protects
new durable work and provider cost; it does not fully protect broker capacity.

## How It Was Verified

Focused tests cover service ordering, replay, rejection, release, API errors,
Redis failure, response validation, and typed boundaries. The project Redis
container executed the exact Lua source and returned two admissions, one rejection
with a 60-second retry, an independent admission for another user, and a bounded
TTL. CI remains offline and no provider call is required.

## What You Must Understand

Level 1: idempotency and rate limiting solve different problems. Replay must stay
available without charging new quota, but a genuinely new key consumes admission.

Level 1: Redis is authoritative only for the temporary window. PostgreSQL remains
authoritative for whether work exists and may be recovered.

Level 1: there is no atomic transaction across Redis and PostgreSQL. Unique
reservation tokens, compensating release, bounded TTL, and conservative failure
semantics make that limitation explicit.

Level 2: the Lua script uses one sorted set per user and Redis `TIME`; the API
maps rejection to 429 and dependency failure to 503.

## Knowledge Check

1. Why must idempotent replay happen before the Redis reservation?
2. Why does a dispatch failure retain the reservation?
3. How does the Lua script prevent two API processes from exceeding the limit?
4. What happens if the process crashes after reservation but before PostgreSQL
   returns a creation result?
5. Why is Redis deletion acceptable even though it resets the current window?
6. Why is this design insufficient for billing or durable monthly quotas?
7. Why can replay remain safe for provider cost while still consuming broker
   capacity?
