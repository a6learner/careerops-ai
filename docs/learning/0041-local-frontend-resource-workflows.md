# 0041 Local Frontend Resource Workflows

## What Changed

P1-9b connected the Experiences and Jobs screens to the existing FastAPI API
through the same-origin Next.js proxy.

- Experiences support create, list, edit, and soft delete.
- Jobs support create, status-filtered cursor pagination, and status updates.
- Resource updates send the version currently shown to the user as `If-Match`.
- Shared feedback distinguishes 401, 409, 429, and 503 responses and retains the
  backend request ID.

No backend route, authorization rule, database behavior, or public API contract
changed.

## Why It Exists

The frontend must expose the existing backend guarantees instead of hiding or
reimplementing them. TanStack Query owns only browser-side server-state
coordination; PostgreSQL and FastAPI remain authoritative.

## Failure Modes It Prevents

- A stale browser tab silently overwriting a newer Experience or Job version.
- Pagination stopping after the first page without telling the user more data exists.
- A 429 being shown as a generic failure with no retry guidance.
- A 401 looking like lost data instead of an expired session.
- A backend request ID disappearing before the user can report a failure.
- Duplicate Experience skills being sent because of case differences.
- Non-HTTP source strings becoming clickable external links.

## How It Was Verified

From `frontend/`:

```powershell
npm run lint
npm run typecheck
npm test
npm audit --omit=dev
npm run build
```

The frontend suite passed 16 tests across 7 files. New tests cover structured
rate-limit failures, Experience create/edit/delete behavior, and Job creation and
status updates with the displayed resource version. The optimized build generated
the Experience and Job routes successfully.

P1-8 backend tests were not repeated because this slice changes no backend code.
No provider was called and no frozen holdout was accessed.

## What You Must Understand

Level 1:

- Optimistic locking prevents lost updates; it does not lock a row while a user
  keeps a browser form open.
- The displayed resource version is the precondition for a PATCH. A 409 means the
  browser must refresh rather than silently retry the stale write.
- Filtering and cursor pagination are backend contracts. The browser must pass the
  opaque cursor back without decoding or modifying it.
- FastAPI still performs authentication and object-level authorization for every
  resource request.

Level 2:

- TanStack Query caches lists, invalidates them after successful mutations, and
  does not retry mutations automatically.
- Forms translate empty optional fields to JSON `null` where the backend contract
  uses null to clear or omit a value.
- The Next.js proxy forwards `If-Match`, `Retry-After`, and `X-Request-ID` across
  the browser/backend boundary.

## Knowledge Check

1. Why does an Experience PATCH use the version from the rendered record?
2. What should the UI do after `EXPERIENCE_VERSION_CONFLICT`?
3. Why must a Job cursor be treated as opaque?
4. Why is TanStack Query not the system of record?
5. Which layer prevents one user from reading another user's Experience?
6. Why is a source URL restricted again before rendering it as a link?
