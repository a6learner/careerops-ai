# PostgreSQL Backup/Restore Drill Test Record

## Scope

This record covers one local P1-8a synthetic PostgreSQL backup/restore drill. It
does not cover real user data, Redis, PITR, replication, cloud storage, managed
databases, production traffic, worker scheduling, or production RTO/RPO.

## Environment And Identity

- Date: 2026-10-06 America/Los_Angeles.
- Branch: `codex/p1-3b-embedding-holdout` with uncommitted P1-8a changes.
- Run ID: `20261006t133000z_4b7d2e61`.
- PostgreSQL server: 16.15, existing `pgvector/pgvector:pg16` Compose service.
- `pg_dump` and `pg_restore`: PostgreSQL 16.15 from the same container.
- Alembic revision restored: `202610060001`.
- Provider inputs: all provider settings forced to fake; zero provider calls.

The source and restore databases were derived from the run ID and used separate
`careerops_p18a_*` names. The dump was stored only in the run-specific system
temporary directory. The development `careerops` database was never a dump source
or restore target.

## Synthetic Data Restored

| Table | Rows |
|---|---:|
| users | 1 |
| experiences | 1 |
| experience_embedding_runs | 1 |
| jobs | 1 |
| parse_runs | 1 |
| job_requirements | 2 |
| analysis_runs | 1 |
| evidence_matches | 2 |
| action_items | 1 |

The fixture included a 1536-dimensional fake embedding with content-hash, model,
input-version, and timestamp provenance; one grounded positive evidence quote; one
gap; and an Action Item derived from that gap.

## Verification

- Restored Alembic revision and all table counts matched the source fixture.
- Experience and Job hashes matched their pre-backup values.
- The positive evidence quote remained an exact substring of the Experience.
- Embedding dimensions and provenance matched the restored Experience content hash.
- Repository reads returned the complete Experience, Job, Parse Run, Analysis Run,
  evidence, and Action Item graph.
- Seven authenticated read-only API requests returned HTTP 200: current user,
  Experiences, Jobs list/detail, Parse Run, Analysis Run, and Action Items.
- PostgreSQL rejected four invalid writes covering Analysis lifecycle CHECK,
  grounded-evidence CHECK, evidence uniqueness, and Action Item foreign key.
- Required named constraints and unique indexes were present after restore.
- Success cleanup removed both temporary databases and the run artifact directory;
  a final catalog and filesystem check found no P1-8a residue.

## Measurements

| Measurement | Result |
|---|---:|
| Custom-format dump size | 36,043 bytes |
| Backup elapsed time | 499 ms |
| Restore elapsed time | 579 ms |
| Restore verification elapsed time | 795 ms |
| End-to-end drill elapsed time | 12,344 ms |

Dump SHA-256:
`92ff50202fbca3a3c09715ac9ef430af9cd04143f94736ce270780c63f3a7e85`.

These are single-run local synthetic measurements. They are not production RTO,
RPO, throughput, reliability, or capacity claims.

## Retained Failure Evidence

The first mutating attempt stopped during synthetic seed because User and Experience
were flushed together without an ORM relationship that communicated dependency
ordering. PostgreSQL correctly rejected the child insert and the transaction rolled
back to zero rows. No dump or restore database was created. After read-only identity,
sentinel, revision, and row-count checks, the author approved exact cleanup. The seed
now explicitly flushes the User before dependent rows; focused tests and quality
gates passed before the successful rerun.
