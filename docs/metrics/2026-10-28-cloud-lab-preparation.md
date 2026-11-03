# Temporary Cloud Lab Preparation — 2026-10-28

## Scope And State

Author authorized preparing a short-lived remote deployment learning exercise,
documenting the work and teaching account registration through teardown. No AWS
resource was created and no cloud account was accessed. The author reports no AWS
account and needs registration guidance. Work remains uncommitted/unpushed.

Baseline HEAD: `975120761ae0a1adfa3577247daf638ca5b72a69`.
New preparation files are working-tree changes. This report uses the author's
America/Los_Angeles date; some raw artifacts use UTC 2026-10-29.

## Delivered

- `docker-compose.cloud-lab.yml`: standalone private single-host topology,
  random database/JWT secrets, production settings, fixed fake providers, bounded
  container logs, separate API/worker/release roles and loopback-only ingress.
- `scripts/cloud_lab.sh`: initialization, config checks, serial builds, ordered
  release, status/logs, bounded recovery, backup/scratch restore and scoped teardown.
- `scripts/test_cloud_lab.sh`: daemon-free shell failure-path verification.
- Operations guide: AWS registration, cost boundaries, SSH, Docker, code transfer,
  browser checks, troubleshooting, evidence collection and resource deletion.
- ADR-043 and learning note 0051: decisions, limitations and Knowledge Check.

## Observed Verification

All container operations selected only project `careerops-cloud-lab`. Existing
`careerops-agent-demo-20261027` resources remained running and were not migrated.
Synthetic accounts and fixture uploads were used; no personal database was copied.

| Check | Actual result |
|---|---|
| Compose resolution | Passed; database/Redis have no published host ports; API/frontend bind 127.0.0.1 only |
| Linux shell syntax and failure tests | Passed; repeat init preserves credentials, mode 0600, rejects public binding, migration failure blocks application startup, release ordering, guarded deletion, pre-existing scratch DB preservation, failed-restore scratch cleanup |
| Image build | API, worker including LibreOffice, frontend built successfully locally |
| Empty database migration | Upgraded to `202610270001`; repeat release migration succeeded |
| Migration drift | `alembic check`: no new upgrade operations detected |
| Browser workflow | Existing Playwright tests: 2 passed; CV import/job discovery/core loop and project source review/confirmation/withdrawal |
| Offline backend | 443 passed, 26 integration cases deselected; explicit fake provider environment |
| Quality gates | Ruff passed; strict mypy passed across 145 source files; both import-boundary contracts kept |
| Linux script runtime | Real daemon-backed check/up/migration/recover/backup/restore-check/destroy actions exercised through a temporary Linux CLI container |
| Backup | Custom-format dump restored into a separate scratch DB; expected Alembic revision observed |
| Data comparison | Every public table compared by row count and ordered full-row JSON digest; all 17 tables equal and nonempty, while source was idle |
| Queue recovery fault | Stopped only lab worker, submitted one queued Parse Run, flushed only lab Redis DB, restarted worker, recovered one dispatch from PostgreSQL; run succeeded at attempt 1 with 2 requirements |
| Readiness limitation | API readiness remained 200 while worker was stopped; demonstrates dependency readiness is not worker correctness |
| Cleanup | Linux destroy action removed only lab containers/network/database volume; final label checks found zero remaining lab resources |
| Transfer archive | Explicit source paths archived and member list checked to exclude env secrets, local dependencies, Git and databases; release package kept locally under ignored `.cloud-lab/` |

Compact evidence: [machine-readable summary](2026-10-28-cloud-lab-preparation.json).
Raw JUnit, image IDs, synthetic dump, comparison and recovery outputs remain under
ignored `.cloud-lab/`; raw paths/hostnames/credentials are not published.
The transfer package SHA is stored with the local package; it will be rechecked
before upload. Its contents include working-tree preparation, not just HEAD.

## Failures And Corrections

- Docker Desktop daemon access required an approved execution context.
- First offline regression: 338 passed, 105 setup errors because Windows default
  pytest temp directory was inaccessible. Project-local temp fixed setup, but
  Windows hard-link/protected-state operations remained restricted: 422 passed,
  21 failed. Same unmodified tests passed with required local permissions (443).
- An initial combined image build ran concurrently despite Compose concurrency
  settings. The cloud build command now builds each service explicitly in sequence.
- Running status inside a tool container cannot reach the host via that container's
  127.0.0.1. Release/migration completed, then status failed at curl. This was a
  verifier network-namespace mismatch. Browser tests on the actual host passed;
  tool-container recovery/backup/restore/cleanup were run separately. Ubuntu-host
  status/curl and SSH connectivity still require the first cloud run.
- Negative shell tests deliberately reject public bindings, duplicate init,
  migration/restore failures and missing deletion acknowledgement. These expected
  rejections are not counted as successful deployment attempts.

## Limits And Next Step

Ready for the author to register an AWS account and inspect Lightsail availability.
Official 2026-10-28 documents support a Free-plan-first registration route when
eligible, with Lightsail in the new experience service list. Actual eligibility,
region, selected package and fees must be checked on the author's account.
No claim of guaranteed free hosting, hard budget cap or cloud completion is made.

The 4 GB candidate has not been capacity-tested on Lightsail. Ubuntu provisioning,
SSH forward, remote image build, remote browser/restore and deletion/billing checks
remain unexecuted. Public HTTPS, automatic recovery scheduling, live models,
remote MCP and formal P1-13/P1-14 completion remain outside this private first lab.
Windows/DPAPI client restrictions remain unchanged. Frozen evaluations were not run;
ordinary offline tests used test doubles and temporary fixture data only.

First user step: register via the official AWS entry, prefer Free plan if offered,
complete the account's verification, and report whether the Lightsail console is
available. Payment details and verification codes stay with the user. Create the
temporary instance only when ready to perform the guided deployment session.

## Readiness Recheck Before Account Registration

The transfer archive was rehashed and every archived regular file was compared
byte-for-byte with the current working tree: all matched. The archive has 311
entries and SHA-256
`7fd395b48e610650dad8a209629d377b8e6c3c83dc08633007482d7e085a0ad5`.
Windows OpenSSH `ssh`, `scp` and `tar` are available. `git diff --check` passed.
No repeated runtime test or new resource creation was necessary for this recheck.

Current external dependency: the author has not yet reported a usable AWS account
or Lightsail console. Registration, account verification and any payment step
require the author's interaction. Remote deployment and its teaching session
remain pending; the overall learning objective is not marked complete.
