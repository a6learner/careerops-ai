# P0 Evidence And Limitations

This matrix is the current source of truth for local P0 closure. “Verified” means
there is saved local or CI-configured evidence. It does not mean cloud or
production verification.

| P0 area | Status | Evidence | Remaining limitation |
|---|---|---|---|
| Authentication and object authorization | Verified with limitation | Auth and cross-user integration tests; ADR-006, ADR-007, ADR-008, ADR-009, ADR-039 | No refresh, logout revocation, or server-side session management; access-token expiry requires login again. |
| Experiences and optimistic locking | Verified | `tests/integration/test_experiences_postgres.py`; Learning 0009 | Local PostgreSQL evidence only. |
| Jobs and cursor pagination | Verified | `tests/integration/test_jobs_postgres.py`; `docs/metrics/2026-10-10-read-endpoint-performance.{md,json}` | At 5,000 synthetic rows the index changed the plan but did not show a DB execution-time improvement; no production capacity claim. |
| Worker-backed parsing | Verified | ADR-010 through ADR-013; parser metrics and P1-10 browser acceptance | Real-provider quality evidence is historical and bounded; normal acceptance remains fake-only. On 2026-10-31 the real parser passed grounding for 2 of 17 full real job descriptions (duplicate candidate IDs from multi-skill sentences; splitter broke decimals and "e.g."). parse-v3 (ADR-046) fixed both, and failed runs now record a reason and tokens. Afterwards 7/7 direct and 3/3 worker parses passed on the same three descriptions (`docs/metrics/2026-10-31-real-data-walkthrough-test-record.md`). Only the first skill per sentence is stored. |
| Evidence matching and integrity | Verified with quality limitation | ADR-014, ADR-015, ADR-023 through ADR-030; frozen holdout and worker-integration evidence | Frozen matcher holdout coverage was 6/8; both partial cases became gaps. Holdout is closed. The DB constraint enforces verdict shape and the application-set `quote_valid` flag; substring, ownership, candidate and version checks are application code. In the 2026-10-31 real-data runs, a single matcher call failed its contract on 3 of 4 attempts for 10–17 requirement jobs; one provider 429 ends a run (no retry); and the matcher under-claimed (one real job: 16 of 16 `missing` despite supporting Experiences). With fake embeddings, hybrid retrieval behaves as lexical only. |
| Action Items and Dashboard | Verified | `docs/metrics/2026-09-12-action-items-test-record.md`; `docs/metrics/2026-09-13-dashboard-test-record.md`; P1-10 acceptance | Dashboard cache hit rate and production load are not measured. |
| Analysis admission limit | Verified | `docs/metrics/2026-10-06-analysis-admission-rate-limit-test-record.md` | Redis is fail-closed for new Analysis Runs; this is a deliberate availability/cost trade-off. |
| Observability and lifecycle integrity | Verified | ADR-032; `docs/metrics/2026-10-06-analysis-run-observability-test-record.md`; lifecycle constraint record | No production log backend, alerting, or SLO evidence. |
| Liveness and readiness | Verified | ADR-033; `docs/metrics/2026-10-06-api-readiness-test-record.md`; P1-10 frontend readiness evidence | Local dependency checks only. |
| Backup and recovery | Verified locally | ADR-034, ADR-035; backup/restore and worker-recovery drill records | Synthetic local data only; no managed-cloud restore evidence. The recovery cycle is never scheduled, refuses non-fake providers, and does not cover CV import or job discovery runs. |
| Fresh database migration | Implemented and locally exercised | CI `migration` job; P1-11 rollback drill begins from blank pgvector DB | The work has been pushed and CI runs on every push, but no GitHub-hosted run result is saved in the repository, so a green run is not claimed. |
| Supported migration rollback | Verified | `docs/metrics/2026-10-10-migration-rollback-drill.md` | Verified on 2026-10-10 for `202610060001 <-> 202609190001`, the head at that time. Later migrations `202610110001` and `202610270001` have downgrade functions but no saved drill, and `scripts/local_migration_rollback_drill.ps1` still asserts the old head, so it must be re-targeted before reuse. No destructive or production downgrade was attempted. |
| Main read P50/P95 | Verified locally | `docs/metrics/2026-10-10-read-endpoint-performance.{md,json}` | Sequential single-machine synthetic measurement; not throughput, concurrency, availability, or production evidence. |
| Browser core loop | Verified locally | ADR-038; `docs/metrics/2026-10-10-local-full-stack-acceptance.md` | All providers fake; no cloud deployment claim. |
| 3–5 minute demo | Verified locally | `docs/demo/p0-demo-script.md`; `docs/metrics/2026-10-10-p0-demo-rehearsal.md` | Automation validates the browser path and pacing; human narration quality remains presenter's responsibility. |
| Cloud deployment | Deferred (public) | Platform-neutral runbook and ADR-036; one private fake-provider lab: ADR-043, `docs/metrics/2026-10-28-cloud-lab-run.md` | Provider, TLS, DNS, production secrets, hosted migrations, and production smoke test are P1-14. The private lab is not public or production evidence. |

## Evidence Rules

- Historical ADRs, learning notes, and metric artifacts are retained even when a
  current summary supersedes their roadmap wording; they are an audit trail.
- A saved local result is never relabeled as CI, cloud, or production evidence.
- Any number used in README, a demo, or a resume must link to a saved artifact.
- Unmeasured production error rate, availability, throughput, cache hit rate, and
  token cost remain `not measured`.
