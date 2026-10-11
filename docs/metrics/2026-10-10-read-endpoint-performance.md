# Read Endpoint Performance — 2026-10-10

## Scope

Local synthetic evidence for the main authenticated read endpoints. This is not production latency, throughput, availability, or capacity evidence.

- Git revision: `dd1b3003547c+working-tree-p1-11`
- Run ID: `20261010b`
- Compose project: `careerops-p111-perf-20261010b`
- Jobs: 5,000
- Cursor traversal: 5,000 unique original Jobs
- Insertion stability: passed
- Percentiles: nearest-rank: sorted[ceil(p * n) - 1]

## Results

| Scenario | Warmups | Samples | P50 ms | P95 ms |
|---|---:|---:|---:|---:|
| `auth_me` | 25 | 200 | 3.727 | 5.839 |
| `experiences_list` | 25 | 200 | 5.698 | 8.107 |
| `experience_detail` | 25 | 200 | 5.394 | 7.476 |
| `jobs_first_page` | 25 | 200 | 6.602 | 9.141 |
| `jobs_deep_cursor_indexed` | 25 | 200 | 7.301 | 9.278 |
| `job_detail` | 25 | 200 | 5.316 | 7.400 |
| `parse_run_detail` | 25 | 200 | 6.964 | 8.975 |
| `analysis_run_detail` | 25 | 200 | 6.998 | 9.003 |
| `action_items_first_page` | 25 | 200 | 8.032 | 10.470 |
| `dashboard_cold` | 0 | 50 | 10.204 | 12.875 |
| `dashboard_warm` | 25 | 200 | 5.080 | 8.530 |
| `jobs_deep_cursor_unindexed` | 25 | 200 | 7.740 | 9.595 |

The raw JSON artifact preserves every timing sample and both indexed and unindexed `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` plans.

## Interpretation

All measured API P95 values were below the product specification's local
200 ms read target. This is single-machine synthetic evidence, not a production
SLO or capacity result.

The indexed deep-cursor request measured 7.301 ms P50 / 9.278 ms P95; after the
Job index was dropped in the disposable database it measured 7.740 ms P50 /
9.595 ms P95. The indexed plan used `idx_jobs_user_status_updated`; the unindexed
plan used a sequential scan plus sort. In the captured database-only plans, the
indexed execution time was 0.857 ms and the unindexed execution time was
0.617 ms. At 5,000 rows this run therefore proves plan selection and a small
API-observed difference, but it does **not** prove a database execution-time
improvement or justify an “A to B optimization” claim.

## Limitations

- Single-machine sequential local measurements are not production capacity evidence.
- The fixture is synthetic and contains no real user data.
- The benchmark measures API-observed latency and does not isolate network, serialization, or database time.
- Dropping the Job index occurs only in the disposable benchmark database.
- The successful harness run removed its exact containers, network, and volume.
