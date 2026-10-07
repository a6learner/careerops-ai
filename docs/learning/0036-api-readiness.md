# 0036 API Readiness

## What Changed

`GET /readyz` now checks PostgreSQL and Redis concurrently. It returns HTTP 200
only when both dependencies are reachable and HTTP 503 otherwise. The response
always identifies each dependency's boolean state.

`GET /healthz` is unchanged and performs no dependency checks.

## Why It Exists

Liveness and readiness answer different operational questions:

- liveness: should the platform restart this process?
- readiness: should the platform send normal traffic to this process?

Returning 200 with a `not_ready` string is insufficient because deployment
platforms normally make routing decisions from the HTTP status. Redis must be in
the readiness contract because queue dispatch and Analysis admission depend on it.

## Failure Modes It Prevents

- Routing traffic to an API that cannot reach PostgreSQL.
- Accepting traffic when queue dispatch or fail-closed Analysis admission cannot
  reach Redis.
- Treating an HTTP 200 response body as an operational failure signal.
- Logging connection strings, credentials, exception text, or user data during a
  dependency outage.
- Restarting a healthy process merely because an external dependency is down.

## How It Was Verified

- Unit tests cover ready/ready, down/ready, ready/down, and down/down.
- Redis adapter tests cover ping success and connection failure.
- A real-container integration test returned ready for local PostgreSQL and Redis.
- JSON logging tests cover the allowlisted dependency booleans.

## What You Must Understand

Level 1: liveness controls restart decisions; readiness controls traffic routing.
A dependency outage should normally remove traffic without restarting a healthy
API process.

Level 2: both checks start concurrently, and the Redis check uses the configured
bounded socket timeouts. Each checker converts infrastructure exceptions into a
boolean at the adapter boundary.

## Knowledge Check

1. Why must `/healthz` avoid checking PostgreSQL and Redis?
2. Why is HTTP 503 necessary even when the body already says `not_ready`?
3. Why is Redis critical for this API even though dashboard caching is fail-open?
4. Why does readiness intentionally exclude the external model provider?
5. What important worker condition is still not proven by this endpoint?
