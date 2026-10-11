# 0040 Local Frontend Session Boundary

## What Changed

P1-9a added a Next.js App Router frontend foundation with a consistent workspace
shell, registration and login pages, an HttpOnly-cookie session, a restricted
same-origin proxy to FastAPI, and frontend quality gates in CI.

Business resource pages are still placeholders. Experience CRUD, Job workflow,
Parse and Analysis polling, Action Items, and live Dashboard counts belong to the
next independently verified slices.

## Why It Exists

The product needs a browser interface, but the browser should not own a reusable
bearer credential or force the backend to accept a broad development CORS policy.
The Next.js server can keep the access token outside browser JavaScript while
preserving the backend as the real authorization boundary.

## Failure Modes It Prevents

- Browser JavaScript reading an access token from local storage.
- A client replacing the trusted Authorization header before proxying.
- Backend cookies or unrelated request headers crossing the proxy boundary.
- Cross-site POST, PATCH, or DELETE requests using the session cookie.
- A backend 429 losing its Retry-After header at the frontend boundary.
- An expired backend token remaining accepted by the frontend proxy.
- UI code treating route hiding as object-level authorization.
- Placeholder Dashboard values being presented as real metrics.

## How It Was Verified

From `frontend/`:

```powershell
npm run lint
npm run typecheck
npm test
npm audit --omit=dev
npm run build
```

The component and policy suite passed 10 tests. ESLint, strict TypeScript, the
production dependency audit, and the optimized Next.js build also passed. The
Windows sandbox initially blocked temporary-file renames and path canonicalization;
the same commands passed with ordinary host permissions. That was an execution
environment limitation, not an application workaround.

## What You Must Understand

Level 1:

- Authentication proves who the caller is; FastAPI object-level authorization
  still decides which resource that caller may access.
- HttpOnly prevents JavaScript from reading a cookie, but does not make XSS or CSRF
  irrelevant.
- SameSite cookies and Origin validation protect a different boundary from backend
  authorization.
- A BFF can translate a cookie-authenticated browser request into a bearer-authenticated
  service request without changing the backend token contract.
- A proxy must allowlist paths and headers; forwarding everything recreates the
  attack surface it was meant to narrow.

Level 2:

- Route Handlers set and clear the host-only session cookie.
- Server Components read the cookie and call `/api/v1/auth/me` before rendering the
  workspace.
- The generic proxy inserts Authorization, preserves If-Match and Idempotency-Key,
  and carries Retry-After and X-Request-ID back to the browser.
- TanStack Query will coordinate server state; PostgreSQL remains authoritative.

## Knowledge Check

1. Why is an HttpOnly cookie safer than local storage for the access token?
2. Why does HttpOnly not eliminate CSRF concerns?
3. Why must the proxy ignore a browser-supplied Authorization header?
4. Which headers must survive the proxy for optimistic locking, idempotency, rate
   limiting, and observability?
5. Why does a protected layout not replace FastAPI object-level authorization?
6. What happens when the current 30-minute token expires without a refresh token?
