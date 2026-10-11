# 0042 Local Frontend Parse Run Workflow

## What Changed

P1-9c added the existing asynchronous Parse Run workflow to each Job card.

- The browser submits `POST /api/v1/jobs/{job_id}/parse-runs` with an
  `Idempotency-Key` through the same-origin proxy.
- The UI polls the returned run while it is queued or running.
- Successful runs display category, normalized skill, and requirement text.
- Failed and cancelled runs remain visible as terminal states.
- A failed dispatch or transport attempt can be retried with the same key.

No backend route, worker behavior, provider selection, database schema, or API
contract changed.

## Why It Exists

Parsing is asynchronous because model-backed work does not belong on the API
request path. The UI therefore needs to represent durable workflow state instead
of treating submission as immediate completion.

## Failure Modes It Prevents

- Creating duplicate Parse Runs when a 503 or network response is retried.
- Treating queued work as completed work.
- Polling forever after a succeeded, failed, or cancelled terminal state.
- Hiding the durable parser error code behind a generic frontend message.
- Displaying requirements when the run failed.
- Inventing historical recovery when the current API has no Parse Run list route.

## How It Was Verified

From `frontend/`:

```powershell
npm run lint
npm run typecheck
npm test
npm audit --omit=dev
npm run build
```

The frontend suite passed 19 tests across 8 files. New tests prove stable
idempotency keys across a 503 retry, successful requirement rendering, and
durable failure presentation without requirements.

P1-8 backend tests and the previously reviewed Parse Run integration suite were
not repeated because this slice changes no backend code. No provider was called
and no frozen holdout was accessed.

## What You Must Understand

Level 1:

- A 202 response means the run was accepted, not that parsing succeeded.
- Idempotency protects retries only when the caller reuses the same key for the
  same logical request.
- `queued` and `running` are non-terminal; `succeeded`, `failed`, and `cancelled`
  are terminal.
- The worker and PostgreSQL own workflow truth. Polling only observes that truth.
- A failed run must not expose requirements as though parsing succeeded.

Level 2:

- TanStack Query uses a 1.5-second interval only while the observed run is
  non-terminal.
- The submission mutation retains its key after request failure and clears it
  after an accepted response.
- A 409 idempotency conflict starts a genuinely new logical request with a new
  key instead of replaying an incompatible one.
- Page refresh cannot recover a prior run because the current public API has no
  list-latest Parse Run route. Adding such a route would require separate approval.

## Knowledge Check

1. Why must a 503 retry reuse the original idempotency key?
2. Why does a 202 response not allow the UI to show requirements immediately?
3. Which statuses stop polling, and why?
4. Why are requirements hidden for `failed` runs?
5. Which component is authoritative for the run state: React Query, Redis, or
   PostgreSQL?
6. Why does refresh recovery require a backend listing contract rather than a
   frontend guess?
