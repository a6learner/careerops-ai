# API Readiness Test Record

## Scope

This record covers P1-7b API readiness for PostgreSQL and Redis. It does not
cover worker heartbeat, automatic recovery scheduling, external model providers,
cloud deployment, backup/restore, or load testing.

## Contract Verified

- `/healthz` remains a dependency-free process liveness check.
- `/readyz` starts PostgreSQL and Redis checks concurrently.
- both ready returns HTTP 200 and `status=ready`;
- either or both unavailable returns HTTP 503 and `status=not_ready`;
- the response reports `database` and `redis` booleans;
- failure logs contain request ID and dependency booleans without connection
  strings, credentials, exception text, or user content.

## Verification

- 8 focused unit tests passed for the endpoint matrix, Redis adapter, JSON log
  allowlist, and unchanged liveness response.
- 1 integration test passed against real local PostgreSQL and Redis containers.
- Default offline suite: 320 passed and 22 infrastructure-gated tests skipped.
- `mypy --strict` passed across 121 source files.
- Ruff and both import-boundary contracts passed.
- No real model provider was configured or called.
