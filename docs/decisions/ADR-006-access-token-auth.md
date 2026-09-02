# ADR-006: Issue Signed JWT Access Tokens For Login

## Status

Accepted

## Context

After registration, the system needs a way for a client to prove which user is making later requests. Experiences, jobs, analysis runs, and action items will all be user-owned resources, so object-level authorization depends on a reliable current-user identity.

The first login slice should establish authentication without introducing refresh-token storage, revocation, or session management complexity too early.

## Decision

Add `POST /api/v1/auth/login` and issue signed JWT access tokens.

Use `PyJWT` with `HS256`, a project-configured `CAREEROPS_JWT_SECRET`, and a default 30-minute expiration. The JWT subject (`sub`) is the user id.

Invalid email and wrong password both return `401 INVALID_CREDENTIALS` with the same message so the API does not reveal whether an email is registered.

Refresh tokens and protected resource dependencies are deferred to later slices.

## Alternatives Considered

- Server-side sessions: easier revocation, but requires session storage before we need it.
- Login plus refresh tokens in the same change: closer to production auth, but too many concepts for one step.
- Different errors for unknown email and wrong password: easier for users, but leaks account existence.
- Unsigned or hand-rolled tokens: unacceptable because clients could tamper with identity claims.

## Consequences

The API can now authenticate users and return a portable bearer token for future protected endpoints.

The token cannot yet be used to access protected resources because current-user extraction is intentionally deferred. Token revocation is also not implemented yet.

## Verification Or Evidence

Unit tests cover token signing, token rejection with a wrong secret, successful login, unknown email rejection, and wrong password rejection.

The PostgreSQL integration test covers registering a real user, logging in with a case-insensitive email, and receiving `401 INVALID_CREDENTIALS` for a wrong password.

## Revisit If

Revisit when adding refresh tokens, logout, token revocation, secret rotation, or deployment-specific secret management.
