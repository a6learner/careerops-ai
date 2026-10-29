# 2026-10-29 UI Polish, Job Detail And Focus Reads: Test Record

Branch `claude/ui-and-product-polish`, based on `ebcc99d`. Local Windows 11
machine, Docker Desktop, fake providers only. These are local results, not CI
or production evidence.

## Backend

| Check | Result |
|---|---|
| `mypy --strict` (145 source files) | passed |
| `ruff check .` | passed |
| `lint-imports` | 2 contracts kept, 0 broken |
| New unit tests (parse/analysis latest, focus date and limit) | passed |
| `tests/integration/test_latest_runs_and_focus_postgres.py` | 2 passed |
| Full suite, `CAREEROPS_RUN_INTEGRATION=1`, Redis `redis://127.0.0.1:6379/0` | 474 passed, 2 skipped, 1 failed |

The one failure is `tests/integration/test_project_agent_cli_postgres.py::test_cli_cross_process_records_review_search_and_replay`
(`httpx.ReadTimeout`). The same test was run against an untouched `ebcc99d`
checkout in a temporary git worktree and failed the same way, so it predates
this branch. Cause not investigated.

An earlier full run with the default `redis://localhost:6379/0` also failed
`test_readiness` and `test_analysis_rate_limit_redis` with Redis connection
timeouts. Both pass with `127.0.0.1`. On this machine `localhost` did not reach
the Docker-published Redis port; this is an environment issue, not a code change.

pytest was run with `--basetemp` inside the session scratch directory because
the sandbox could not write to the default system temp folder.

## Frontend

| Check | Result |
|---|---|
| `npm run lint` | passed |
| `npm run typecheck` | passed |
| `npm test` (Vitest) | 19 files, 43 tests passed |
| `npm run build` | passed; `/jobs/[id]` route built |

New or changed component tests cover:

- restoring the latest Parse Run and Analysis Run after a reload without submitting work;
- board status changes with `If-Match`;
- the withdraw confirmation step;
- dashboard focus links;
- the job-not-found state and that an unsafe source URL is never linked.

## Full-stack browser acceptance

`scripts/local_full_stack_acceptance.ps1 -RunId ui20261029`:

```json
{
  "providers": {"parser": "fake", "embedding": "fake", "matcher": "fake", "job_search": "fake"},
  "migration": "passed",
  "core_loop": "passed",
  "browser_elapsed_seconds": 18.1,
  "cleanup": "passed"
}
```

Both Playwright specs passed (`2 passed`). The core loop now:

- opens the job detail page from the board;
- changes the status from the property menu;
- reloads the page and checks that the parsed requirements and the evidence quote are still shown.

The elapsed time is a single local run and is not a performance claim.

## Screenshots

`docs/design/2026-10-28-redesign-preview/` holds 14 screenshots: 7 pages, each at
desktop (1440px) and phone (400px) width. They were captured with
`frontend/scripts/capture-preview.mjs` against a production build, the local API
and worker, and synthetic seeded data.

## Not measured

Performance of the new read endpoints was not measured. No accessibility audit
tool was run; accessibility was checked only through labelled controls and role
queries in tests.
