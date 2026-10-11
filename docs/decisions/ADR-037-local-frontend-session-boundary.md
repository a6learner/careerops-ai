# ADR-037: Local Frontend And Same-Origin Session Boundary

## Status

Accepted

## Context

P1-8 completed the local backend operational foundation, but the product core
loop still required direct API use. P1-9 needs a presentable Next.js demo layer
without changing backend authentication, authorization, public API contracts, or
CORS policy.

The backend issues a 30-minute bearer access token and does not yet implement a
refresh token. Storing that bearer token in browser local storage would expose it
to any successful same-origin script injection. Calling FastAPI directly from a
separate browser origin would also require a new CORS contract.

## Decision

Place the frontend in `frontend/` using Next.js App Router and TypeScript. Use
Tailwind CSS plus a small, locally owned component layer inspired by shadcn/ui.
TanStack Query is the server-state boundary for later polling, cache invalidation,
and mutation status; it is not used as an application-domain source of truth.

Use Next.js as a same-origin backend-for-frontend:

- login and registration use dedicated Route Handlers;
- a successful login stores the access token in a host-only HttpOnly,
  SameSite=Lax cookie with the same 30-minute lifetime as the backend token;
- production cookies are also `Secure`;
- browser code never receives or stores the bearer token;
- the generic proxy accepts only `/api/v1` resource roots used by the frontend,
  injects its own Authorization header, and never forwards a browser-supplied
  Authorization or Cookie header;
- unsafe methods require an exact same-origin `Origin` header;
- only Content-Type, If-Match, and Idempotency-Key request headers cross the
  boundary;
- Content-Type, Retry-After, and X-Request-ID are preserved on responses;
- a backend 401 clears the frontend session cookie.

FastAPI remains the final authentication, authorization, validation, concurrency,
and evidence-integrity boundary. Hiding a frontend action is never treated as
authorization.

## Alternatives Considered

- Browser local-storage bearer token: simpler proxying, but exposes the token to
  browser JavaScript and requires direct cross-origin API access.
- Broad CORS between Next.js and FastAPI: rejected because it creates a new public
  browser-origin contract only to support local development.
- A third-party authentication framework: rejected because the backend already
  owns credential verification and token issuance; adding a second identity
  system would duplicate responsibility.
- A large UI framework or global client-state store: rejected because the current
  product needs a small editable component set and server-state polling, not a
  second application architecture.
- Native fetch with handwritten polling on every page: possible, but duplicates
  terminal-state stopping, invalidation, and request-state behavior across Parse
  and Analysis workflows.

## Consequences

The browser has one origin and cannot read the bearer token. The Next.js server
becomes a security-sensitive API boundary and must keep its path, header, origin,
and cookie tests.

The current backend has no refresh-token endpoint, so expiration requires another
login. SameSite=Lax and exact Origin checks reduce cross-site mutation risk but do
not replace FastAPI authorization or ordinary XSS prevention. P1-10 subsequently
added the frontend container and local network topology. Cloud topology remains
deferred to P1-13.

The selected `eslint-config-next` dependency currently brings an unpatched
development-only glob-parser advisory. The runtime dependency audit is clean. A
forced audit fix would downgrade the config across a major compatibility boundary,
so the project records the limitation and will update when a compatible upstream
release is available.

## Verification Or Evidence

- Unit and component tests cover cookie flags, exact-origin mutation checks,
  allowlisted proxy paths, request/response header filtering, structured API
  errors, login, registration ordering, and failed credentials.
- Frontend strict TypeScript, ESLint, Vitest, production dependency audit, and the
  optimized Next.js build pass locally.
- CI installs the lockfile and runs those same frontend gates independently from
  the existing backend matrix.
- Evidence is recorded in
  `docs/metrics/2026-10-08-local-frontend-foundation-test-record.md`.

## Revisit If

- A later stage reopens the ADR-039 refresh-token deferral with a separately
  approved session-lifecycle design.
- Multiple public origins become a real deployment requirement.
- A measured frontend workflow demonstrates that TanStack Query is insufficient.
- Next.js publishes a compatible ESLint dependency chain that resolves the
  recorded development-only advisory.
