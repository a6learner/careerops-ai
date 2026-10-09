# ADR-036: Platform-Neutral Deployment Contract

## Status

Accepted

## Context

The backend has tested API, worker, PostgreSQL, Redis, readiness, backup, and work
recovery paths, but the original image omitted Alembic files, installed the
project in editable mode, and ran as the image default user. Compose did not
provide a complete API plus migration startup path.

A deployable contract must remain independent of a cloud vendor and must not let
every API or worker replica race to run schema migrations.

## Decision

Build one immutable image containing application code and Alembic migrations.
Install the package non-editably and run it as the unprivileged `careerops` user.
Resolve runtime dependencies through the checked-in Python 3.11 Linux constraints
captured from the verified image; dependency updates require intentional review
and another deployment rehearsal.
The same image supports three explicit process roles:

- release: `alembic upgrade head`;
- API: Uvicorn serving `careerops.main:create_app`;
- worker: Dramatiq serving `careerops.workers.tasks`.

Migration is a one-shot release step. API and worker processes start only after
that step succeeds in the local Compose topology. They never run DDL during
application startup.

The image liveness check calls `/healthz`; the Compose API readiness check calls
`/readyz`, which requires PostgreSQL and Redis. Production configuration rejects
the checked-in development JWT secret. `.dockerignore` allowlists only the files
required to build the image, so ignored local secrets are not sent in the build
context.

## Alternatives Considered

- Run Alembic inside every API startup: rejected because concurrent replicas can
  race and deployment rollback becomes ambiguous.
- Build separate API and worker images: rejected because both use the same code
  and dependencies; separate commands are sufficient for this monolith.
- Add platform-specific manifests now: deferred until the author selects a cloud
  provider, managed PostgreSQL/Redis offering, cost boundary, and public ingress.
- Put provider live gates in Compose defaults: rejected because a durable `.env`
  value must not authorize an external model call.

## Consequences

The image is reusable across ordinary container platforms, but a production
release still needs external PostgreSQL, Redis, secret injection, TLS/ingress,
log collection, and a platform-specific rollback procedure. The container health
check proves process liveness; readiness proves only PostgreSQL and Redis
connectivity, not worker consumption or model-provider availability.

## Verification Or Evidence

- Configuration tests prove production rejects the documented local JWT secret.
- CI builds the deployment image after backend checks pass.
- The P1-8d isolated Compose rehearsal builds from scratch, migrates an empty
  database, starts API and worker roles, verifies health/readiness and non-root
  identities, reruns the migration idempotently, and removes its project resources.
- Measured local evidence is stored in
  `docs/metrics/2026-10-06-container-deployment-rehearsal.md`.

## Revisit If

- A platform requires a different port or health-probe command.
- API and worker dependencies diverge enough to justify separate images.
- A zero-downtime migration requires an expand/contract release sequence.
