# 0039 Platform-Neutral Deployment Contract

## What Changed

CareerOps now has one non-root deployment image for the API, worker, and release
migration roles. Compose can start a complete fake-provider stack, with API and
worker startup gated on a successful one-shot migration. CI builds the image.

Production settings reject the checked-in development JWT secret. The Docker
build context is an allowlist containing only package and migration inputs. The
verified Python 3.11 Linux runtime dependency graph is constrained explicitly.

## Why It Exists

Passing application tests does not prove the artifact can be released. Deployment
needs a defined image, process roles, schema transition, readiness contract,
secret boundary, and rollback decision point.

## Failure Modes It Prevents

- Shipping an image that cannot run Alembic.
- Multiple API replicas racing to apply migrations.
- Starting application processes after a failed migration.
- Running the service as the image default root user.
- Using the documented local JWT secret in production.
- Sending `.env`, Git history, virtual environments, or local artifacts into the
  Docker build context.
- Rebuilding the same revision against silently changed dependency versions.
- Treating process liveness as proof that PostgreSQL and Redis are usable.

## How It Was Verified

Unit tests cover the production-secret rule. Static checks validate the Compose
model and Python code. An isolated Compose project builds the real image, creates
a fresh PostgreSQL volume, applies all migrations, starts fake-only API and worker
containers, checks liveness/readiness and user IDs, reruns Alembic, and removes the
containers, network, and volume.

## What You Must Understand

Level 1: schema migration is a release concern, not an API startup side effect.
Deploy migration first, then start code that expects the new schema.

Level 1: liveness answers whether a process should be restarted; readiness answers
whether it should receive traffic. Neither proves that a worker is consuming jobs.

Level 2: one image can safely run multiple process roles when the code and
dependencies are identical and commands remain explicit.

Level 2: non-root execution reduces container privilege, while secret injection
keeps environment-specific credentials outside the image.

## Knowledge Check

1. Why must migrations not run independently in every API replica?
2. Why does `/healthz` intentionally avoid PostgreSQL and Redis?
3. Why does `/readyz` still not prove worker health?
4. Why is `.dockerignore` an information-security control as well as a build optimization?
5. What must be checked before rolling application code back after a migration?
