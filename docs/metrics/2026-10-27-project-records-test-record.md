# Project Records: Initial Incremental Upgrade Test Record

Date: 2026-10-27 (America/Los_Angeles).
Baseline: `381ef0e`, branch `codex/p1-3b-embedding-holdout`.
Implementation and this record are uncommitted. Author acceptance is pending.

## Scope And Boundaries

Add project/checkpoint API, bounded source snapshots, review and search UI to the
existing product. No existing Experience, Job, Parse, Analysis, Action Item or
Dashboard contract is replaced. MCP, Skill, automatic recording, Notion and
resume generation are not implemented. No new server-side model call exists.

All data in this verification is synthetic. Provider behavior is explicitly fake.
No frozen holdout or live provider evaluation is run. The development database
is not migrated; only isolated disposable databases are used.

## Backend And Database Verification

- Ruff over `src tests migrations`: passed.
- Strict mypy: passed for 138 source files.
- Import Linter: both dependency contracts kept.
- Full backend regression: **414 passed, 2 skipped**, with PostgreSQL and Redis.
  Raw result: [final JUnit](2026-10-27-project-records-pytest-final.xml).
- After adding extra competing-review assertions, the focused module run passed
  **19 tests**. Raw result: [focused JUnit](2026-10-27-project-records-focused.xml).
  Application code was unchanged between the full and final focused runs.
- Fresh Alembic upgrade through `202610270001`: passed.
- Model/migration drift check: no new upgrade operations.
- New one-step downgrade to `202610110001`, re-upgrade and drift check: passed
  on the disposable `careerops-k2-20261027-pg` database only. This is not a
  production rollback or retention test.

Command shape (environment variables set only for each test process):

```powershell
$env:CAREEROPS_DATABASE_URL='postgresql+asyncpg://careerops:careerops@127.0.0.1:25427/careerops'
$env:CAREEROPS_REDIS_URL='redis://127.0.0.1:26327/0'
$env:CAREEROPS_LLM_PROVIDER='fake'
$env:CAREEROPS_EMBEDDING_PROVIDER='fake'
$env:CAREEROPS_EVIDENCE_MATCHER_PROVIDER='fake'
$env:CAREEROPS_RUN_INTEGRATION='1'
.\.venv\Scripts\python -m pytest --tb=short -x `
  --basetemp=.pytest_cache/k2-20261027-full `
  --junitxml=docs/metrics/2026-10-27-project-records-pytest-final.xml
```

This command documents the historical invocation. Use new report/temp paths for
a future run; do not overwrite historical evidence. The temporary services are
not a persistent development environment.

Direct assertions cover:

- concurrent project and checkpoint creation converges to one record;
- changed payload with the same key returns 409;
- all new resource paths enforce ownership, including linked project writes;
- invalid quotes, empty sources, unsafe locators, null characters and oversized
  UTF-8 packets are rejected;
- a database CHECK independently rejects missing/ungrounded source quotes;
- the composite owner FK rejects a cross-user checkpoint insertion;
- snapshots cannot be modified even through direct SQL;
- initial inserts must be drafts, and withdrawn records cannot be revived;
- identical review retries converge; competing contribution notes yield one
  success and one conflict rather than overwriting each other;
- missing/stale preconditions fail, and confirmation needs a contribution note;
- literal substring search treats `%` literally; cursor pages have distinct IDs;
- withdrawal excludes records from confirmed search, while save replay returns
  the same withdrawn record; no formal Experience is created.

## Frontend And Security Patch

Final frontend uses Next.js / eslint-config-next **16.4.3**, patched from 16.4.0.
The initial production build stopped with a security warning. `npm audit` confirmed
the affected package; the [official advisory](https://nextjs.org/blog/nextjs-security-update-october-14-2026)
recommends patched 16.4 versions. The update stays in the existing release line.

After the patch:

- ESLint: passed.
- TypeScript: passed.
- Vitest: **17 files, 37 tests passed**.
- Production build: passed, including `/projects` alongside all previous routes.
- `npm audit --omit=dev`: **0 vulnerabilities**.
- The installation's full audit reports **4 development findings (2 moderate,
  2 high)**; they are unresolved and no clean full-audit claim is made.

New UI tests prove explicit contribution is required, displayed If-Match is
forwarded, a lost-response retry reuses its submission key, and withdrawn history
has no confirmation/resurrection controls. Proxy tests retain the existing
authorization/header policy and add only the Projects resource root.

## Browser Acceptance

Initial isolated full-stack run `projectrecords20261027` passed both Chromium
scenarios and cleaned its Compose resources. A second run against the final
security-patched lockfile uses:

```powershell
.\scripts\local_full_stack_acceptance.ps1 `
  -RunId projectrecordspatch20261027 `
  -PostgresPort 25428 -RedisPort 26328 -ApiPort 28028 -FrontendPort 23028
```

Final patched acceptance: passed. Both Chromium tests passed; fresh migration,
fake provider checks, frontend non-root UID 1000 and exact Compose cleanup passed.
The harness measured 15.3 seconds around the browser command; Playwright reported
13.6 seconds for its two tests. These are local execution observations, not a
product performance or time-saving claim. The captured summary is saved in
[browser result](2026-10-27-project-records-browser.json).

Scenarios:

1. Original browser core loop: CV upload/review, fake job discovery/full-description
   confirmation, Parse, Analysis, evidence/gaps, Action Items, status and Dashboard.
2. New Projects: register, create project, save a source-grounded draft, require
   contribution, confirm, reload, select project, search confirmed records, inspect
   exact quote, withdraw and verify exclusion/history. Existing navigation remains.

## Failures Preserved And Resolved

- Docker was initially stopped and installed outside the standard Program Files
  path. Started the existing installation; no replacement was installed.
- Sandbox localhost access timed out; approved unsandboxed commands reached the
  exact temporary services. This was not an application correctness failure.
- JSONB whole-document search incorrectly used `.astext`; changed to an explicit
  SQL Text cast, then the integration scenario passed.
- Old Dashboard tests force Redis port 6379. Verified it was unused and provided
  a labeled temporary compatibility container rather than changing old assertions.
- System pytest Temp access failed. The failed report remains
  [here](2026-10-27-project-records-pytest.xml); the final run uses an isolated
  workspace cache directory and retains the same tests.
- Sandboxed Vitest failed before executing tests because a temporary cache rename
  was denied. An approved unsandboxed run passed; no tests were disabled.
- The initial Next.js security warning was verified and patched, not suppressed.

## Remaining Limits

No host/MCP compatibility, automatic capture completeness, generated resume
quality, cloud availability, production retention, or performance improvement is
measured. Source hashes establish payload identity, not truth, authorship or
independent test execution. Corrections use withdrawal plus a new draft; explicit
replacement links, deletion UI and gap linkage remain future slices.

Temporary standalone database/Redis cleanup: passed after inspecting the exact
`careerops.run=k2-20261027` labels. Removed the three named containers and their
temporary anonymous volumes; label-filtered enumeration returned no residue.
Only synthetic test data was discarded; source and verification reports remain.
