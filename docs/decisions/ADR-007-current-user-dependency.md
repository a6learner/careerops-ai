# ADR-007: Current User Dependency

## Status

Accepted

## Context

Authenticated endpoints need a reliable way to answer "who is making this
request?" without duplicating token parsing, database lookup, or error mapping in
every route.

The project also has a strict layering rule: API code should coordinate HTTP
concerns, service code should own business decisions, and repository code should
own persistence.

## Decision

Use a FastAPI dependency to read and validate the `Authorization: Bearer <token>`
header, then delegate token verification and user lookup to `AuthService`.

The service verifies the JWT, extracts the user id from the token subject, loads
the user from PostgreSQL, and rejects the request when the token is missing,
malformed, expired, invalid, or points to a user that no longer exists.

## Alternatives Considered

- Decode the token directly inside each route: rejected because it would spread
  authentication logic across endpoint files.
- Let the API dependency call the repository directly: rejected because the API
  layer would start making business decisions that belong in the service layer.
- Trust the JWT subject without checking the database: rejected because deleted
  or invalid users could still appear authenticated until token expiry.

## Consequences

Protected routes can share one current-user path. Tests can override the
dependency when a route does not need to exercise authentication itself.

Every protected request performs a database lookup. This is acceptable for the
MVP because PostgreSQL is the source of truth and correctness matters more than
avoiding one small query.

## Verification Or Evidence

- Unit tests cover token verification and dependency failure paths.
- Integration tests cover `/api/v1/auth/me` with real PostgreSQL.
- `pytest`, `mypy --strict`, Ruff, and import-boundary checks pass locally.

## Revisit If

Revisit if protected endpoint volume becomes high enough that the database
lookup is measured as a bottleneck, or if authorization grows enough to require a
separate policy layer.
