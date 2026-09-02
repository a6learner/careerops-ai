# ADR-005: Implement Registration Through API, Service, And Repository Layers

## Status

Accepted

## Context

Registration is the first endpoint that writes user-owned data. It touches HTTP request validation, password hashing, PostgreSQL persistence, unique email constraints, and error semantics.

Putting all of that directly in a FastAPI route would make the route hard to test and would blur the boundary between transport concerns and business behavior.

## Decision

Implement registration through three explicit layers:

- API layer: validates HTTP input and returns HTTP responses.
- Service layer: hashes the password and coordinates user creation.
- Repository layer: performs SQLAlchemy persistence and translates database uniqueness failures into a domain error.

The endpoint is `POST /api/v1/auth/register`. It returns `201 Created` with public user fields only. Duplicate email registration returns `409 EMAIL_ALREADY_REGISTERED`.

Login and JWT issuance are intentionally deferred to the next authentication slice.

## Alternatives Considered

- Put all logic in the route: faster initially, but weaker separation and harder tests.
- Add login and JWT in the same change: more product progress, but too many new concepts at once.
- Check duplicate email only before inserting: user-friendly, but incomplete under concurrency because two requests can pass the check at the same time.

## Consequences

Registration has a clear path for future authorization work. Password hashing is not scattered through route code, and duplicate email behavior is ultimately guarded by the database unique constraint.

The trade-off is a few extra small files. That is acceptable because the layers map to concepts the author needs to understand and explain.

## Verification Or Evidence

Default tests cover request validation and service behavior without requiring Docker.

An optional PostgreSQL integration test covers successful registration and duplicate email rejection against the real `citext` unique constraint.

## Revisit If

Revisit if the layering becomes too heavy for simple CRUD endpoints or if a future unit-of-work abstraction is introduced for multi-repository transactions.
