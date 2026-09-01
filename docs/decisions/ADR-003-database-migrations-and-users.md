# ADR-003: Manage Database Schema With Alembic

## Status

Accepted

## Context

CareerOps AI depends on PostgreSQL as the system of record. Authentication, object-level authorization, optimistic concurrency, async run state, evidence validation, and metrics all rely on database tables and constraints that must be reproducible from a clean environment.

Hand-written setup instructions or ad hoc SQL in local databases would make the project hard to review, test, deploy, and explain.

## Decision

Use Alembic to version PostgreSQL schema changes.

The first migration creates the `users` table and enables PostgreSQL `citext` so email uniqueness is case-insensitive at the database layer.

Application models use SQLAlchemy 2.0 declarative mappings. Migrations remain explicit files under `migrations/versions/` so schema changes can be reviewed and rolled back.

## Alternatives Considered

- Let SQLAlchemy create tables automatically at startup: convenient locally, but it hides schema changes and is unsafe for production-style workflows.
- Keep raw SQL setup scripts only: simple, but no migration history or downgrade path.
- Delay migrations until business tables exist: faster today, but it would postpone the database discipline this project is meant to demonstrate.

## Consequences

Database changes become visible, reviewable, and repeatable.

The cost is extra ceremony: every schema change needs a migration file and verification. That ceremony is intentional because database constraints are part of the project's engineering signal.

## Verification Or Evidence

The migration can be inspected with `alembic history` and applied with `alembic upgrade head` once PostgreSQL is running.

The SQLAlchemy `users` metadata is covered by `tests/test_models.py`.

## Revisit If

Revisit only if the project stops using PostgreSQL as the system of record or moves to a framework that provides an equivalent explicit migration system.
