# Platform-Neutral Deployment Runbook

## Scope

This runbook defines the release contract before a cloud platform is selected. It
does not provision PostgreSQL, Redis, TLS, DNS, backups, or monitoring.

## Required Inputs

- An immutable image built from the intended Git revision.
- The reviewed `constraints/deployment-py311-linux.txt` used by that image build.
- PostgreSQL with pgvector and a tested backup/restore path.
- Disposable Redis reachable by API and worker processes.
- A deployment-specific `CAREEROPS_JWT_SECRET` supplied through a secret store.
- Explicit provider selections. Keep all providers `fake` for offline rehearsals.
- Separate authorization before enabling any real-provider worker gate.

## Release Order

1. Record the image digest and current Alembic revision.
2. Confirm a recent backup/restore drill and the database rollback boundary.
3. Run exactly one release process: `alembic upgrade head`.
4. Require a zero exit code and verify `alembic current` reports the expected head.
5. Start or replace API containers.
6. Wait for `/healthz` and then `/readyz` to return HTTP 200.
7. Start or replace worker containers with the intended provider configuration.
8. Run one synthetic smoke flow or inspect an already authorized queued item.
9. Observe structured errors, queue recovery results, and dependency readiness.

## Failure And Recovery

- Migration fails: do not start the new API or worker image. Preserve the migration
  output, inspect the transaction state, and restore only through the documented
  database recovery procedure.
- API live but not ready: inspect the bounded PostgreSQL/Redis readiness booleans;
  do not route traffic until both are true.
- Redis loses messages: run the bounded recovery cycle; PostgreSQL remains the
  source of truth.
- Worker crashes after claiming work: wait past the configured stale threshold,
  then run the recovery cycle. Attempt fencing prevents the stale worker from
  committing over the recovered attempt.
- Provider fails: keep the durable failure. Do not silently substitute fake output.

## Rollback Boundary

Rolling back an image is safe only when the previous code understands the current
database schema and queued message shapes. Do not automatically downgrade Alembic.
For an incompatible migration, use an explicitly reviewed expand/contract plan or
restore the database according to the separately tested recovery procedure.

## Local Rehearsal

Use a unique Compose project and a non-default host port so existing development
containers are not selected:

```powershell
$env:CAREEROPS_API_PORT = "18080"
$env:CAREEROPS_POSTGRES_PORT = "15432"
$env:CAREEROPS_REDIS_PORT = "16379"
docker compose --project-name careerops-p18d up -d --build
docker compose --project-name careerops-p18d ps
Invoke-RestMethod http://127.0.0.1:18080/healthz
Invoke-RestMethod http://127.0.0.1:18080/readyz
docker compose --project-name careerops-p18d run --rm migrate
docker compose --project-name careerops-p18d exec -T api id
docker compose --project-name careerops-p18d exec -T worker id
docker compose --project-name careerops-p18d down --volumes
Remove-Item Env:CAREEROPS_API_PORT
Remove-Item Env:CAREEROPS_POSTGRES_PORT
Remove-Item Env:CAREEROPS_REDIS_PORT
```

Before deletion, verify the exact Compose project name. `down --volumes` is only
appropriate for the isolated rehearsal project, never for a development or
production project whose PostgreSQL volume must be retained.
