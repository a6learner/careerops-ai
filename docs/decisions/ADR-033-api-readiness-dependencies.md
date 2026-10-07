# ADR-033: API Readiness Dependencies

## Status

Accepted

## Context

The API exposes separate liveness and readiness endpoints. Liveness already
answers whether the API process is running. Readiness previously queried only
PostgreSQL and returned an HTTP 200 response even when that query failed.

Redis is also required for essential API behavior: worker dispatch and Analysis
admission control cannot safely accept new work without it. A load balancer must
not route normal traffic to an API instance that reports either durable storage
or queue/admission infrastructure as unavailable.

## Decision

`GET /healthz` remains process-only and performs no dependency calls.

`GET /readyz` checks PostgreSQL and Redis concurrently. It returns HTTP 200 only
when both checks succeed. Otherwise it returns HTTP 503 and a bounded response:

```json
{"status":"not_ready","database":true,"redis":false}
```

Failure logs contain request ID and dependency booleans only. They do not contain
database URLs, Redis URLs, credentials, exception messages, or user data.

The Redis check reuses the API process's existing client and configured bounded
socket timeouts. Readiness remains observational: it does not repair dependencies,
requeue work, or mutate PostgreSQL or Redis.

## Alternatives Considered

- Keep database-only readiness: rejected because Redis failure prevents queue
  dispatch and makes Analysis admission fail closed.
- Return 200 with `not_ready`: rejected because orchestrators and load balancers
  use the HTTP status, not application-specific JSON semantics.
- Include provider availability: rejected because providers are worker-only and
  readiness probes must not create network calls, cost, or provider coupling.
- Include worker heartbeat: deferred because no durable heartbeat contract or
  scheduler exists yet; inventing one would expand this slice.

## Consequences

- Redis failure now removes an API instance from readiness even though cached
  dashboard reads alone could fail open.
- The readiness response adds a `redis` boolean, and dependency failure now uses
  the already documented HTTP 503 response.
- Both dependency checks begin together, so a slow failed dependency does not
  delay starting the other check.
- This endpoint proves connectivity only. It does not prove that a worker is
  consuming messages or that recovery commands are scheduled.

## Verification Or Evidence

- Unit tests cover all four PostgreSQL/Redis readiness combinations and their
  HTTP status codes.
- Redis checker tests cover successful ping and connection failure.
- Integration testing calls the endpoint with real local PostgreSQL and Redis
  containers.
- Structured logging tests confirm dependency booleans are emitted through the
  existing allowlist.

## Revisit If

- A deployment platform requires separate shallow and deep readiness probes.
- Worker heartbeat or queue-depth evidence becomes a defined operational contract.
- Measured probe volume requires connection or result caching.
