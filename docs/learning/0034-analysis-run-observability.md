# 0034 Analysis Run Observability

## What Changed

Analysis Runs now emit valid, allowlisted JSON events from durable acceptance
through dispatch, worker claim, terminal completion, stale-attempt fencing, and
recovery. Initial queue delivery carries the validated HTTP request ID, while run
ID and attempt remain the durable correlation identity.

## Why It Exists

An asynchronous failure crosses process and time boundaries. A request ID alone
cannot describe work that PostgreSQL later recovers, and a run status alone does
not explain how that state was reached. The three identifiers answer different
questions:

- request ID: which invocation emitted this event;
- run ID: which durable operation is being diagnosed;
- attempt: which execution generation produced or lost the write race.

## Failure Modes It Prevents

- Logs that look like JSON but break when a message contains quotes.
- Structured fields being attached to a record but omitted from output.
- A client injecting unsafe or unbounded request-ID text into logs.
- Losing the API-to-worker correlation at queue publication.
- Confusing duplicate delivery with a second provider execution.
- Confusing a stale worker's fenced write with the current attempt's outcome.
- Debug logging exposing Experience/JD text, tokens, credentials, or raw provider
  output.

## How It Was Verified

Focused tests parse emitted JSON, confirm non-allowlisted raw content is absent,
exercise request-ID replacement, inspect submission/dispatch/worker/recovery
correlation, and prove old one-argument Analysis messages remain accepted.

The integration path remains fake-only. PostgreSQL is used for durable state and
attempt fencing; Redis carries only disposable delivery context.

## What You Must Understand

Level 1: `run_id + attempt`, not request ID, is the durable asynchronous identity.
Recovery is a new invocation with a new request ID.

Level 1: structured logs are diagnostic evidence, not the source of truth. Losing
logs cannot change whether a run exists or whether a stale attempt may commit.

Level 2: queue arguments added during deployment need defaults so already-published
messages do not fail after workers upgrade.

Level 2: the formatter uses an explicit field allowlist. Adding a field to a
`logger` call does not make it externally visible until the privacy boundary also
permits it.

## Knowledge Check

1. Why can the original HTTP request ID not identify a later recovery invocation?
2. What does attempt fencing protect when two workers log the same run ID?
3. Why must the Analysis actor accept an old message containing only a run ID?
4. Why are response hash and size safer than raw provider output?
5. Which failures would still be diagnosable if Redis and all logs were deleted?
