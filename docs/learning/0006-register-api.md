# 0006 Registration API

## What Changed

This step added the first user-facing write endpoint:

```text
POST /api/v1/auth/register
```

The endpoint accepts an email and password, hashes the password, writes a user row, and returns only public user fields.

New files:

- `src/careerops/api/auth.py`
- `src/careerops/db/session.py`
- `src/careerops/domain/errors.py`
- `src/careerops/domain/users.py`
- `src/careerops/repositories/users.py`
- `src/careerops/schemas/auth.py`
- `src/careerops/services/auth.py`
- `tests/test_auth_schemas.py`
- `tests/test_auth_service.py`
- `tests/integration/test_auth_register_postgres.py`

## Why It Exists

The project needs user accounts before it can enforce object-level authorization. Every future resource, such as experiences and jobs, will belong to a user.

Registration is split across layers:

```text
API -> service -> repository -> PostgreSQL
```

The route handles HTTP. The service handles business behavior. The repository handles database persistence.

## Failure Modes It Prevents

- Returning `password_hash` by accident.
- Storing raw passwords.
- Letting duplicate emails create two accounts.
- Encoding database errors directly into route code.
- Mixing HTTP framework objects into business logic.

## How To Verify It

Default checks:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

With PostgreSQL running:

```powershell
docker compose up -d postgres
.\.venv\Scripts\alembic upgrade head
$env:CAREEROPS_RUN_INTEGRATION = "1"
.\.venv\Scripts\python -m pytest tests/integration/test_auth_register_postgres.py
Remove-Item Env:\CAREEROPS_RUN_INTEGRATION
```

## What You Must Understand

Level 1 concepts:

- API contracts define success and failure behavior.
- Database unique constraints are the final guard against duplicate emails.
- `409 Conflict` means the request shape is valid but conflicts with current system state.

Level 2 concepts:

- Pydantic validates and normalizes request data.
- SQLAlchemy `AsyncSession` is the database conversation for a request.
- Repository code owns SQLAlchemy details.
- Service code coordinates business behavior and does not import FastAPI.

## Knowledge Check

1. Why does duplicate email return `409` instead of `422`?
2. Why is checking for an existing email before insert not enough under concurrency?
3. Why should `AuthService` not import `Request`, `Depends`, or `HTTPException`?
4. Why does the response include `id`, `email`, and `created_at`, but not `password_hash`?
5. Why is the PostgreSQL integration test optional in default `pytest`?
