# Database Migrations

Alembic migrations live here. Each migration is a versioned database change that can be applied from an empty PostgreSQL database and reviewed like application code.

Run migrations after starting PostgreSQL:

```powershell
docker compose up -d postgres
alembic upgrade head
```

Inspect the current migration state:

```powershell
alembic current
```
