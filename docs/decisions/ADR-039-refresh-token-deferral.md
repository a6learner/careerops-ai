# ADR-039: Defer Refresh Tokens From The Local MVP

## Status

Accepted

## Context

The backend issues a 30-minute JWT access token. The Next.js backend-for-frontend
stores it in a host-only HttpOnly cookie, and an expired token requires the user
to log in again. The original product specification listed
`POST /api/v1/auth/refresh`, but no refresh-token storage, rotation, revocation,
reuse detection, logout, or session-management contract was approved or built.

P1-11 must either define that security-sensitive contract or record the missing
capability honestly. The local MVP can complete its core loop within one access
token lifetime, so refresh is not required to demonstrate the current product.

## Decision

Defer refresh tokens, token revocation, and server-side session management from
the MVP. Do not advertise or document `/auth/refresh` as an implemented endpoint.

The known limitation is explicit: after the 30-minute access token expires, the
frontend clears the session after a backend 401 and the user must log in again.
This decision does not change the existing login, cookie, authentication, or
authorization contracts.

## Alternatives Considered

- Add a long-lived refresh JWT immediately: rejected because safe rotation,
  storage, reuse detection, revocation, and logout semantics require a separate
  authentication design and security review.
- Extend the access-token lifetime: rejected because it increases exposure after
  theft and hides the missing session lifecycle rather than solving it.
- Add a server-side session store: viable later, but it changes the accepted
  authentication architecture and is not needed for local P0 acceptance.

## Consequences

The local demo has a bounded 30-minute authenticated session and may require a
new login if the presenter waits too long. There is no silent refresh, logout
revocation, multi-device session view, or immediate stolen-token invalidation.

Cloud deployment must not proceed on the assumption that refresh exists. A later
implementation requires its own ADR, threat model, public API contract, database
or session-store design, and authorization/security tests.

## Verification Or Evidence

- The API surface contains registration, login, and current-user endpoints, but
  no refresh endpoint.
- Frontend session tests verify the HttpOnly access-token cookie and clearing on
  backend 401.
- The P0 evidence matrix records re-login after expiry as an accepted MVP
  limitation.

## Revisit If

- A cloud release requires sessions longer than 30 minutes.
- Logout revocation, multi-device sessions, or compromised-token response becomes
  a product requirement.
- The author approves a separate authentication design and risk review.
