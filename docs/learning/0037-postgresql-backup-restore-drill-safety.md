# 0037 PostgreSQL Backup/Restore Drill Safety

## What Changed

P1-8a now has a typed resource planner and an explicitly gated synthetic recovery
drill. It derives isolated source and restore database names, a fixed temporary dump
path, a manifest, and database comment sentinels from one strict run ID.

The drill migrates and seeds a temporary source database, creates a PostgreSQL custom
archive, restores it into a distinct empty database, verifies data and behavior, and
cleans up only after exact identity checks. Redis and model providers are excluded.

## Why It Exists

A restore drill eventually needs destructive cleanup permission. Because the local
Compose role can create and delete databases, safety cannot depend on an operator
not making a typo. Deletion targets must be derived, narrow, and independently
identifiable.

## Failure Modes It Prevents

- Treating `careerops`, `postgres`, or a template database as a drill target.
- Escaping the fixed temporary directory with path traversal.
- Following a symbolic link or Windows reparse point during later cleanup.
- Cleaning resources from a different run because a name was copied incorrectly.
- Treating a dry-run plan as backup/restore evidence.
- Hiding failed-drill diagnostics through automatic cleanup.
- Reporting a successful restore when hashes, evidence grounding, provenance,
  constraints, repository reads, or API reads were not verified.

## How To Verify It

Run the focused unit tests and inspect a dry-run plan before any real drill. A real
run additionally requires the invocation-local gate and exact cleanup confirmation.
On success, confirm that neither temporary database nor the run artifact directory
remains.

The completed synthetic run restored Alembic head `202610060001`, all expected rows,
hashes, evidence and embedding provenance, repository/API reads, and four negative
constraint checks. The saved metrics record contains the measured local timings.

## What You Must Understand

Level 1: backup correctness and cleanup safety are separate properties. A valid
dump does not make a broad or weakly identified `DROP DATABASE` safe.

Level 2: the manifest records expected identity, while PostgreSQL comments provide
an independently read server-side sentinel. Cleanup requires both.

Level 2: `pg_dump` success alone is insufficient. The destination must be an empty,
separate database and restored application behavior must be verified.

Level 2: SQLAlchemy needs an explicit flush between synthetic parent and child rows
when the mapped models have no ORM relationship that communicates insert ordering.

## Knowledge Check

1. Why are both a manifest and PostgreSQL database comments required?
2. Why is the development database protected even when a caller supplies its name intentionally?
3. Why does a failed drill retain its temporary resources by default?
4. Why are row counts alone insufficient recovery evidence?
5. Why must the local elapsed times not be called production RTO or RPO?
