# 0002 Database Migrations And The Users Table

## What Changed

This step added the first real database foundation:

- `alembic.ini`: Alembic's project-level configuration.
- `migrations/env.py`: connects Alembic to this project's settings and SQLAlchemy metadata.
- `migrations/versions/202608310001_create_users.py`: creates the first table.
- `src/careerops/db/models.py`: defines the SQLAlchemy `User` model.
- `tests/test_models.py`: checks that the `users` table metadata matches the intended contract.
- `docs/decisions/ADR-003-database-migrations-and-users.md`: records the migration decision.

The `users` table has:

- `id`: UUID primary key.
- `email`: case-insensitive unique email using PostgreSQL `citext`.
- `password_hash`: stored password hash, not the raw password.
- `created_at`: database timestamp.

## Why It Exists

Database schema is part of the system's contract. If the API expects a `users` table but the database was created by memory or manual commands, the project becomes hard to reproduce.

Alembic gives us a versioned history:

```text
empty database -> migration 202608310001 -> users table exists
```

This matters for local setup, CI, deployment, rollback, and interviews.

## Failure Modes It Prevents

- A teammate pulls the project and cannot recreate the database.
- Production and local databases quietly drift apart.
- Email uniqueness works in application code but can be bypassed by direct database writes.
- Future auth code assumes a table shape that the database does not actually have.

## How To Verify It

Local checks:

```powershell
pytest
mypy
ruff check .
lint-imports
```

Migration chain check:

```powershell
alembic history
```

Offline SQL rendering:

```powershell
alembic upgrade head --sql
```

In this run, offline SQL rendering produced the expected PostgreSQL DDL:

- `CREATE EXTENSION IF NOT EXISTS citext`
- `CREATE TABLE users`
- primary key `pk_users`
- unique email constraint `uq_users_email`
- Alembic version row for `202608310001`

When PostgreSQL is running:

```powershell
docker compose up -d postgres
alembic upgrade head
alembic current
```

The real database migration was later verified after Docker Desktop was started:

```powershell
docker compose up -d postgres
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\alembic current
docker compose exec -T postgres psql -U careerops -d careerops -c "\dt"
docker compose exec -T postgres psql -U careerops -d careerops -c "\d users"
```

Verified results:

- Alembic current revision: `202608310001 (head)`
- Tables present: `alembic_version`, `users`
- `users.email` type: `citext`
- Constraints present: `pk_users`, `uq_users_email`
- API readiness: `GET /readyz` returned `{"status": "ready", "database": true}`

## What You Must Understand

Level 1 concepts:

- PostgreSQL is the system of record.
- Database constraints protect persisted data even if application code has a bug.
- Migrations make schema changes reviewable and reproducible.

Level 2 concepts:

- SQLAlchemy models describe tables to Python code.
- Alembic migrations apply concrete DDL to PostgreSQL.
- `citext` makes `User@Email.com` and `user@email.com` compare as equal in PostgreSQL.

## Knowledge Check

1. Why is `alembic upgrade head` different from importing the SQLAlchemy `User` model?
2. Why should email uniqueness live in the database instead of only in Python code?
3. What problem does PostgreSQL `citext` solve for login and registration?
4. Why do we create only the `users` table in this step instead of all MVP tables at once?
5. If a migration succeeds locally but fails in CI, what kind of project risk does that reveal?
