# 0008 Current User Dependency

## What Changed

The backend now has `GET /api/v1/auth/me`, a protected endpoint that returns the
currently authenticated user.

The request must include:

```text
Authorization: Bearer <access_token>
```

FastAPI reads the header through a dependency. The dependency checks the header
shape, then asks `AuthService` to verify the token and load the user from the
database.

## Why It Exists

Most real backend features are user-specific. Before we create experiences, job
descriptions, tasks, or application statuses, the backend needs a reusable and
testable way to know which user owns the request.

This is the bridge between login and authorization.

## Failure Modes It Prevents

- Missing token: the request is rejected before business logic runs.
- Wrong header scheme: `Basic abc` or random text is not treated as a JWT.
- Expired token: old login sessions stop working after their configured lifetime.
- Forged token: a token signed with the wrong secret is rejected.
- Deleted user: a valid-looking token is rejected if the user no longer exists in
  PostgreSQL.

## How To Verify It

Run the normal local checks:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

Run the integration test with Docker PostgreSQL:

```powershell
docker compose up -d postgres
.\.venv\Scripts\alembic upgrade head
$env:CAREEROPS_RUN_INTEGRATION='1'
.\.venv\Scripts\python -m pytest tests\integration\test_auth_register_postgres.py
Remove-Item Env:\CAREEROPS_RUN_INTEGRATION
docker compose stop postgres
```

## What You Must Understand

Level 1: authentication is not just "the token decodes." A reliable backend also
checks that the token belongs to a real current user in the system of record.

Level 2: FastAPI dependencies are reusable request-time functions. They are a
good place to translate HTTP details into typed application objects, such as
`UserAccount`.

Level 2: The service layer owns business decisions. The API dependency reads the
header, but `AuthService` decides whether the token maps to a valid user.

## Knowledge Check

1. Why do we check PostgreSQL after decoding a valid JWT?
2. What is the difference between a missing token and an invalid token?
3. Why should protected routes receive a `UserAccount` instead of parsing the
   `Authorization` header themselves?
4. If `/api/v1/auth/me` returns 401 for a token that worked yesterday, what are
   two likely causes?
