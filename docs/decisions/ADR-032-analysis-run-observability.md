# ADR-032: Analysis Run Observability

## Status

Accepted

## Context

Analysis Runs are durable and attempt-fenced, but their operational history could
not be reconstructed from logs. HTTP responses had a request ID, while queue
messages carried only the run ID. The existing log format resembled JSON but did
not escape messages or serialize structured `extra` fields.

The observability slice must diagnose asynchronous failures without adding a
monitoring service, persisting transient HTTP identifiers, or logging user or
provider content.

## Decision

Use `run_id` as the durable Analysis correlation identity and `attempt` as the
execution generation. `request_id` identifies one HTTP, worker delivery, or
recovery invocation. Initial and idempotent-replay dispatches pass the validated
HTTP request ID through the queue. Recovery creates a new request ID and retains
the same run ID; this reflects the real lifecycle instead of pretending that one
HTTP request owns every future recovery attempt.

Analysis queue messages now include run ID, request ID, and dispatch source. The
actor keeps defaults for the new fields so messages published before deployment
with only a run ID remain executable.

Emit allowlisted JSON events for durable acceptance, dispatch success or failure,
worker delivery, claim, duplicate or terminal claim skip, success, durable
failure, stale-attempt fencing, requeue, and recovery summary. Terminal events
include available latency and token counts. Matcher-output diagnostics retain
only failure category, structural location/type, response hash, and byte size.

Incoming request IDs are accepted only when they use a bounded safe character
set. Invalid or oversized values are replaced with a server-generated UUID.

Logging is observational only. A log failure must not change database
transactions, idempotency, queue recovery, provider selection, or attempt
fencing. PostgreSQL remains the source of truth.

## Alternatives Considered

- Persist the submission request ID: rejected because recovery is a separate
  invocation and `run_id + attempt` already provides durable identity.
- Add OpenTelemetry, Prometheus, or a hosted logging service: rejected because
  P1-7a needs a locally testable diagnostic contract, not new infrastructure.
- Use only request ID for correlation: rejected because it cannot survive broker
  publication loss and PostgreSQL-driven recovery without persistence.
- Log raw provider output for debugging: rejected because it may contain user
  evidence and is unnecessary when safe hashes and structural diagnostics exist.

## Consequences

Operators can search one Analysis run ID and reconstruct acceptance, queueing,
attempt claims, terminal results, and recovery. Request ID still connects the
initial API and queue delivery, but it is intentionally not a permanent run
identifier.

Queue payload shape changes internally while remaining backward compatible. No
migration, public API change, provider call, retrieval change, or new dependency
is required.

This slice does not add queryable aggregate metrics or extend the event contract
to Parse and Embedding runs. Those remain separate work.

## Verification Or Evidence

Unit tests cover JSON validity and field allowlisting, unsafe request-ID
replacement, submission/dispatch correlation, terminal and duplicate-delivery
events, recovery attempt correlation, and legacy one-argument worker messages.
Redis, PostgreSQL, and fake-worker integration verify the changed internal queue
contract and existing attempt lifecycle without a provider request.

## Revisit If

- A tracing backend requires W3C trace context.
- Operational policy requires durable linkage to the original HTTP request.
- Measured log volume requires sampling or a dedicated collector.
- Parse and Embedding diagnostics need the same event contract.
