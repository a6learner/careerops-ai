# Analysis Run Observability Test Record

## Scope

This record covers P1-7a Analysis Run structured logging and correlation. It
does not cover aggregate metrics, Parse or Embedding observability parity,
production traffic, or the proposed Analysis lifecycle database constraint.

## Behavior Verified

- application events serialize as valid JSON with an explicit field allowlist;
- raw, non-allowlisted output is not serialized;
- unsafe or oversized external request IDs are replaced with server UUIDs;
- accepted Analysis work records request ID, user ID, run ID, attempt, pipeline,
  model, status, and creation/replay outcome;
- queue delivery carries run ID, request ID, and dispatch source;
- old one-argument Analysis messages receive safe local correlation and remain
  executable;
- worker claim, success, durable failure, duplicate claim skip, and stale-attempt
  fencing use run ID plus attempt;
- recovery creates a new request ID, returns the incremented attempt, logs each
  requeue, and redispatches with recovery as the source;
- safe matcher-output hashes and structural diagnostics remain available without
  raw provider output;
- no migration, public API response change, retrieval change, matcher contract
  change, or new dependency was introduced.

## Verification

Run on 2026-10-06 from branch `codex/p1-3b-embedding-holdout`, based on
`8b611f1b0bc10d35bc015c7af84bcf0bc5da2e43` with uncommitted P1-7a changes.

- 314 default offline tests passed; 21 infrastructure-gated tests skipped.
- focused observability and Analysis lifecycle tests passed.
- 2 PostgreSQL Analysis Run integration tests passed.
- 1 Redis queue-payload integration test passed.
- 1 API-to-Dramatiq-to-PostgreSQL E2E passed after the host process forced all
  providers to fake, the worker parser was explicitly forced to fake, and the
  persisted matcher and embedding identities were verified as fake.
- corrected worker logs showed delivery, claim, and success as valid JSON with
  the same request ID and run ID, attempt 1, and no provider HTTP request.
- `mypy --strict` passed across 120 source files.
- Ruff, both import-boundary contracts, and `git diff --check` passed.

Host integration URLs used explicit `127.0.0.1` PostgreSQL and Redis endpoints to
avoid the known unreachable IPv6 `localhost` path.

## Verification Incident

The first rebuilt Compose worker inherited `CAREEROPS_LLM_PROVIDER=groq` from the
developer `.env`. Three worker-E2E attempts therefore sent the synthetic Parse
input to Groq before recent logs exposed the mismatch. No real matcher or
embedding call occurred, and no real resume or job description was used.

The worker was stopped, recreated with an explicit process-level fake parser
override, and its environment was inspected before rerunning the E2E. Fresh
worker logs contained no provider HTTP request. The E2E now also asserts the
persisted fake parser and embedding model identities, and README instructions
state that both the test process and worker must be forced to fake.

This incident is retained because the earlier calls cannot be described as an
offline verification. It also demonstrates why ambient `.env` values are not a
sufficient test-safety boundary.

## Boundaries

`run_id + attempt` is the durable correlation identity. Request ID identifies a
single HTTP, delivery, or recovery invocation and is not persisted. Logs remain
diagnostic only; PostgreSQL state and attempt-fenced writes are authoritative.
