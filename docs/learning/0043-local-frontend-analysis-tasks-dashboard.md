# 0043 Local Frontend Analysis, Tasks, And Dashboard

## What Changed

The final P1-9 slice completed the browser core loop against the existing API.

- A succeeded Parse Run can start and poll an Analysis Run.
- Succeeded Analysis results align saved matches to parsed requirements.
- Positive evidence is displayed only when the backend persisted a matched or
  partial verdict with `quote_valid=true`.
- Partial, missing, and insufficient-evidence results can create sourced Action
  Items.
- Action Items support manual creation, status filtering, cursor pagination, title
  edits, and status updates.
- Dashboard cards and pipeline counts come directly from `/api/v1/dashboard/summary`.
- 409 feedback distinguishes stale versions, analysis preconditions, idempotency
  conflicts, and non-actionable sources.

No backend route, database semantics, authorization behavior, worker selection, or
public API contract changed.

## Why It Exists

The frontend must complete the user-visible loop without weakening the backend's
evidence or concurrency guarantees. It is a projection and command surface over
durable backend state, not a second source of truth.

## Failure Modes It Prevents

- Showing an unvalidated quote as positive evidence.
- Presenting a missing or insufficient-evidence result as a match.
- Retrying a logical Analysis or Action Item request with a new idempotency key
  after an ambiguous transport failure.
- Silently overwriting an Action Item edited from another client.
- Showing invented Dashboard counts or a single unsupported match score.
- Treating every 409 as a stale-version error.
- Continuing to poll Analysis after a terminal state.

## How It Was Verified

From `frontend/`:

```powershell
npm run lint
npm run typecheck
npm test
npm audit --omit=dev
npm run build
```

The final frontend suite passed 27 tests across 12 files. New coverage proves
validated quote rendering, gap-to-task provenance, durable Analysis failures,
manual Action Item creation, optimistic Action Item updates, real Dashboard
counts, stable Action Item retry keys, Analysis precondition feedback, and 429
retry guidance.

No real model was called and no frozen holdout was accessed. Existing backend and
P1-8 test evidence was not repeated because P1-9 changes only the new frontend,
CI configuration, and documentation.

## What You Must Understand

Level 1:

- The UI does not decide whether evidence is grounded. It renders the verdict,
  quote, version, and validation result already persisted by the backend.
- A partial verdict has some validated evidence but remains actionable as a gap.
- `missing` and `insufficient_evidence` are different safe-negative outcomes; neither
  may display a positive quote.
- Analysis admission can fail with 409, 429, or 503 for different reasons. Those
  statuses must not be collapsed into one retry policy.
- Action Item provenance links preparation work back to the evidence-match result
  that made it actionable.
- Dashboard values are cached projections; PostgreSQL remains authoritative and
  Redis remains disposable.

Level 2:

- TanStack Query polls only non-terminal work and invalidates Action Item and
  Dashboard queries after successful mutations.
- `If-Match` carries the Action Item version currently displayed in the browser.
- Idempotency keys are retained across failed submissions and cleared after an
  accepted response.
- The frontend maps Analysis matches to Parse requirements by UUID and Experience
  labels by owned Experience UUID.

## Knowledge Check

1. What four conditions must be true before the UI displays a positive quote?
2. Why can a partial match create an Action Item?
3. Why must a 429 retry preserve the same logical Analysis request?
4. What prevents a stale Action Item edit from overwriting a newer one?
5. Why does TanStack Query invalidation not make Redis or the browser authoritative?
6. Which P1-9 limitation is intentionally deferred to P1-10?
