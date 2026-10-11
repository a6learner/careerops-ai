# 0044 Local Full-Stack Acceptance

## What Changed

The Next.js standalone server now runs in Compose with the existing one-shot
migration, FastAPI, Dramatiq worker, PostgreSQL, and Redis services. The browser
continues to call only the Next.js BFF; the BFF reaches FastAPI through the
internal Compose DNS name.

A PowerShell harness creates a fresh isolated Compose project, forces all AI
adapters to deterministic fakes, starts the stack, runs one Chromium core-loop
test, and removes the project's containers, network, and volume even on failure.

## Why It Exists

Component tests cannot prove that image builds, migration ordering, cookies,
public and private network addresses, queue delivery, worker execution, and
browser rendering agree. P1-10 exercises those boundaries together while keeping
the test deterministic and free of model cost.

## Failure Modes It Prevents

- Accidentally using a real parser, embedding, or matcher selected by an ignored
  developer `.env` file.
- Starting API or worker before the database migration succeeds.
- Marking a worker unhealthy because it inherited an API-only HTTP probe.
- Rejecting valid browser mutations because an internal container address was
  compared with the public browser Origin.
- Reporting the frontend ready while PostgreSQL, Redis, or FastAPI is unavailable.
- Running the frontend container as root.
- Cleaning a development database or unrelated Compose resources after a failed
  acceptance run.
- Declaring success from direct API calls while the actual browser workflow is
  broken.

## How To Verify It

Install the pinned browser once, then run the isolated harness from the repository
root:

```powershell
Set-Location frontend
npx playwright install chromium
Set-Location ..
.\scripts\local_full_stack_acceptance.ps1 -RunId localcheck
```

Success reports `migration`, `core_loop`, and `cleanup` as `passed`, a non-zero
frontend UID, and all providers as `fake`.

## What You Must Understand

Level 1:

- Liveness answers whether a process can respond; readiness answers whether it
  should receive traffic. Frontend readiness therefore depends on API readiness,
  while frontend liveness does not.
- Internal service discovery (`http://api:8000`) and the browser-visible origin
  are different security concepts.
- PostgreSQL remains the source of truth and Redis remains disposable even though
  the browser test crosses both.
- Deterministic fake providers make the system integration claim reproducible;
  they do not measure real-model quality.
- Cleanup is part of acceptance because an isolated test must not leak state into
  the next run or delete state it does not own.

Level 2:

- Compose `service_completed_successfully` gates API/worker on the one-shot
  migration, while health conditions gate dependent services on readiness.
- The worker overrides the shared image healthcheck because it exposes no HTTP
  server.
- Playwright runs outside the production image and uses only the frontend's public
  URL; same-origin assertions catch accidental direct FastAPI browser traffic.
- The acceptance override and runtime checks both enforce fake provider selection.

## Knowledge Check

1. Why are `CAREEROPS_API_BASE_URL` and `CAREEROPS_FRONTEND_ORIGIN` intentionally different in Compose?
2. Why is disabling the API healthcheck correct for the worker but not for the API?
3. Why does the harness validate provider values both before and after startup?
4. What does the successful fake-provider browser loop prove, and what does it not prove?
5. Why must cleanup filter by the exact Compose project label?
