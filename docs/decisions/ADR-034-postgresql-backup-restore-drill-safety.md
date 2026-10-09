# ADR-034: PostgreSQL Backup/Restore Drill Safety Boundary

## Status

Accepted

## Context

PostgreSQL is the CareerOps system of record, but the repository has no repeatable
recovery drill. A local drill needs permission to create and eventually delete
databases and files. The Compose database role is intentionally powerful for local
development, so a typo or reused database name would create an unacceptable risk.

The drill must prove recovery from an isolated synthetic database without reading,
overwriting, or restoring into the development database.

## Decision

Every drill run uses a strict run ID and derives all resource names from it. Source
and restore databases live only in the `careerops_p18a` namespace. The application
database, PostgreSQL maintenance database, and template databases are permanently
protected.

Artifacts will live only below a fixed system-temporary root. Existing symbolic
links or Windows reparse points in that path are rejected. The dry-run command
prints the complete resource plan without creating the directory.

Cleanup must match four identities: the confirmation run ID, the typed
manifest, the derived database names, and role-specific PostgreSQL database comment
sentinels. A mismatch is a refusal, not a warning. Failed drills retain resources
for diagnosis and require separate cleanup authorization.

Execution also requires an invocation-local opt-in. The source database is migrated
from base to the current Alembic head and seeded only with deterministic synthetic
records. The existing PostgreSQL 16 container creates a custom-format dump. Restore
targets a distinct empty temporary database and uses `--single-transaction` plus
`--exit-on-error`.

Verification checks the Alembic revision, table counts, content hashes, evidence
grounding, embedding provenance, named constraints and indexes, repository reads,
authenticated read-only API paths, and direct FK/CHECK/UNIQUE rejection. Redis and
model providers are not involved.

## Alternatives Considered

- Reuse the `careerops` database: rejected because a recovery drill must never risk
  overwriting development data.
- Accept caller-provided database names and paths: rejected because flexibility
  weakens the deletion boundary without helping the defined local drill.
- Delete all temporary resources automatically on failure: rejected because it
  removes diagnostic evidence and can turn an initial failure into an unsafe cleanup.
- Add a backup tool or managed service: rejected because PostgreSQL 16.15 already
  supplies the required tools inside the existing container.

## Consequences

The workflow is deterministic, testable offline, and deliberately inflexible. A
dry-run proves only safety planning. Only a completed restore with verification is
recovery evidence. Failed runs intentionally require an additional cleanup step.

## Verification Or Evidence

Focused unit tests cover exact name/path derivation, malformed run IDs, protected
database names, cleanup confirmation, manifest and sentinel mismatches, and the
non-mutating dry-run output.

The synthetic drill `20261006t133000z_4b7d2e61` completed backup, restore,
verification, and exact cleanup. Its measurements and limitations are recorded in
`docs/metrics/2026-10-06-postgresql-backup-restore-drill.md`.

## Revisit If

- The drill moves away from local Docker Compose.
- PostgreSQL roles no longer have permission to create isolated databases.
- A production recovery policy introduces encrypted storage, retention, or RTO/RPO.
