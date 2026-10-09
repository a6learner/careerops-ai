# Worker Recovery Cycle Drill — 2026-10-06

## Scope

This is local synthetic operational evidence for one bounded P1-8b recovery cycle.
It is not a production reliability, throughput, RTO, or RPO measurement.

- Run ID: `20261006t173000z_6c8dae2f`
- PostgreSQL: temporary `careerops_p18b_*` database on the existing local Compose server
- Redis: one labeled temporary `redis:7-alpine` container with a random loopback port
- Worker: one dedicated Dramatiq process with one worker process and four threads
- Providers: parser, embedding, and evidence matcher all forced to deterministic fake adapters
- Real provider calls: none
- Development database or existing Redis selected: no

## Synthetic Failure State

- One Parse Run was `running`, attempt 1, and older than the 30-second stale threshold.
- One Analysis Run was `running`, attempt 1, and older than the threshold.
- One active Experience had no Embedding Run and no embedding.
- A separate embedded Experience supplied stable retrieval evidence for Analysis.

## Recovery Result

| Recovery type | Reconciled | Requeued | Dispatched | Dispatch failed | Final attempt |
|---|---:|---:|---:|---:|---:|
| Parse | 0 | 1 | 1 | 0 | 2 |
| Analysis | 0 | 1 | 1 | 0 | 2 |
| Embedding | 1 | 0 | 1 | 0 | 1 |

- Recovered Parse requirements persisted: 2
- Recovered Analysis evidence matches persisted: 1
- All three target runs reached `succeeded`.
- Total local drill elapsed time: 6,337 ms.

## Cleanup Evidence

- Temporary database comment matched `careerops-p1-8b:<run-id>` before deletion.
- Temporary Redis container label matched the exact run ID before stop/removal.
- Dedicated Windows worker process tree was stopped by its owned parent PID.
- Follow-up inspection found no `careerops_p18b_*` database, no P1-8b Redis container,
  and no artifact directory for the successful run.

## Boundary

The elapsed time includes local resource creation, migration, seeding, recovery,
worker startup, polling, and cleanup. It must not be presented as application
latency or production recovery time. The fixture contains only synthetic data and
the deterministic fake adapters do not measure provider behavior.
