# Analysis Admission Rate Limit Test Record

## Scope

This record covers P1-6 per-user admission control for new Analysis Runs. It
verifies API, service, PostgreSQL, and Redis behavior without a provider call.
It does not measure production traffic, provider cost savings, or throughput.

## Behavior Verified

- new Analysis Runs reserve a per-user sliding-window slot before persistence;
- the default configuration is five new runs per 3,600 seconds;
- idempotent replay bypasses admission and returns the existing run;
- a same-key concurrency loser releases its own reservation;
- rejection creates no run and dispatches no task;
- HTTP 429 contains `ANALYSIS_RATE_LIMITED`, `Retry-After`, and structured wait
  seconds;
- Redis reservation failure is fail-closed with HTTP 503;
- release removes only the unique reservation token and is best effort;
- successful PostgreSQL creation retains its slot before dispatch;
- the limiter key is versioned and isolated by authenticated user;
- no migration, worker behavior, retrieval parameter, matcher contract, or
  successful API response shape changed.

## Verification

Run on 2026-10-06 from branch `codex/p1-3b-embedding-holdout`, based on
`fde9a4bb798d5c5775919e1483126e0ea7f495e2` with uncommitted P1-6 changes.

- 311 default offline tests passed; 21 infrastructure-gated tests skipped.
- 2 PostgreSQL Analysis Run integration tests passed with an explicit in-memory
  allowing limiter and the deterministic fake matcher.
- 3 Redis/PostgreSQL integration tests passed in 1.42 seconds using explicit
  `127.0.0.1` container endpoints.
- focused P1-6 tests passed within the default suite, including direct reservation
  lifecycle checks for repository failure and post-commit dispatch failure.
- `mypy --strict` passed across 120 source files.
- Ruff passed.
- both import-boundary contracts passed across 120 files and 360 dependencies.
- `git diff --check` passed.

The automated Redis integration issued three concurrent reservations for one user.
Exactly two succeeded and one returned a bounded retry delay; another user was
admitted independently. The exact Lua source was also executed inside the healthy
project Redis container. With a limit of two and a 60-second window, the observed
sequential diagnostic results were:

- first user, first reservation: allowed;
- first user, second reservation: allowed;
- first user, third reservation: rejected with 60 seconds to retry;
- second user: allowed independently;
- first-user key TTL after execution: 59,577 ms.

The temporary Redis keys were deleted after the check.

## Environment Finding

The first host-run Redis test timed out because `.env` used `localhost`, which
resolved to IPv6 `::1` in the current Windows environment. Docker's IPv4 published
ports were healthy, while the IPv6 localhost path timed out. Re-running with
temporary `127.0.0.1` Redis and PostgreSQL URLs completed all three integration
tests in 1.42 seconds. The temporary environment overrides were removed afterward.

## Boundaries

Redis is disposable admission state, not a durable quota or billing ledger.
Clearing Redis resets the current window. A crash after reservation but before a
known PostgreSQL outcome may conservatively consume one slot until expiry. No
exactly-once cross-store transaction or provider-wide TPM scheduling is claimed.
Queued replay may still publish duplicate broker messages; conditional worker
claiming prevents duplicate provider execution, but full broker-capacity
protection is not claimed.
