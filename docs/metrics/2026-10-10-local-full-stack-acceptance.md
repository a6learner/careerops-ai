# Local Full-Stack Acceptance — 2026-10-10

## Scope

This record closes P1-10 local acceptance for the existing product core loop.

- Branch: `codex/p1-3b-embedding-holdout`
- Base HEAD: `dd1b300`
- Environment: Docker Desktop on Windows, isolated Compose project and volume
- Browser: pinned Playwright Chromium
- Parser, embedding, and matcher: deterministic `fake`
- Real-provider calls: none
- Frozen holdout access: none
- Manual database changes: none
- P1-8/backend full-suite or P1-9 component-suite rerun: none

## Accepted Topology

The browser calls the Next.js origin only. Next.js reaches FastAPI at
`http://api:8000` over the Compose network. The one-shot migration, API, worker,
PostgreSQL, Redis, and frontend remain separate services. No permissive CORS or
Nginx layer was added.

## Final Run

The final clean run used:

```powershell
.\scripts\local_full_stack_acceptance.ps1 -RunId 20261010f
```

Observed result:

```json
{
  "run_id": "20261010f",
  "project": "careerops-p110-20261010f",
  "frontend_url": "http://127.0.0.1:13010",
  "providers": {
    "parser": "fake",
    "embedding": "fake",
    "matcher": "fake"
  },
  "migration": "passed",
  "frontend_user": "uid=1000",
  "core_loop": "passed",
  "cleanup": "passed"
}
```

Playwright completed one test in 6.6 seconds after the stack was ready. That is
execution evidence for this run, not a latency benchmark or performance claim.

## Browser Core Loop

The test completed all of the following through the frontend:

1. Register and establish the HttpOnly session.
2. Create an Experience containing Python evidence.
3. Create a Job requiring Python and Kubernetes.
4. Submit and poll Parse to success.
5. Submit and poll Analysis to success.
6. Verify a grounded Python quote and a Kubernetes gap.
7. Create an Action Item from that gap.
8. Update and reload the Job as `applied`.
9. Update and reload the Action Item as `done`.
10. Verify Dashboard applied/done counts.
11. Assert every observed browser HTTP request remained on the frontend origin.

## Additional Checks

| Check | Result |
|---|---|
| Resolved API and worker provider configuration | all three providers `fake` |
| Running API and worker provider environment | all three providers `fake` |
| Migration release step | exited 0 before API/worker startup |
| Frontend runtime identity | non-root `uid=1000` |
| Frontend `/healthz` | passed |
| Frontend `/readyz` delegated to API readiness | passed |
| Production dependency audit | 0 vulnerabilities |
| Focused health/readiness/session tests | 7 passed across 3 files |
| ESLint | passed |
| Strict TypeScript | passed |
| Frontend production/container build | passed |
| Exact project cleanup | no labeled container, network, or volume remained |

The full development-dependency audit still contains five high-severity reports
in the existing Next.js ESLint dependency chain. The production dependency audit
is clean; no forced incompatible downgrade was applied.

## Corrected Acceptance Failures

Four unsuccessful isolated runs were cleaned before the final result:

- `20261010a`: the worker inherited the API HTTP healthcheck and could never be
  healthy. Compose now disables that probe for the non-HTTP worker role.
- `20261010b`: unsafe mutations compared the public browser Origin with the
  frontend container's internal request URL. A validated canonical public origin
  is now explicit configuration and invalid values fail closed.
- `20261010c`: the product reached Analysis success, but the test expected exact
  text instead of the rendered quoted evidence. The assertion now targets the
  semantic blockquote.
- `20261010d`: the product created the sourced Action Item, but the test selected
  a hidden duplicate status option. Persistence is now verified by reloading and
  checking the actual select value.

Each failed run used the same exact-project cleanup boundary and left no accepted
state behind.

## Boundaries

- This proves a deterministic local integration path, not production reliability,
  availability, throughput, or real-model quality.
- No backend API, schema, migration, authorization, evidence validation, or
  provider contract changed.
- Existing P1-8 and P1-9 evidence was referenced rather than repeated.
- P1-11 closure work and cloud deployment remain out of scope.
