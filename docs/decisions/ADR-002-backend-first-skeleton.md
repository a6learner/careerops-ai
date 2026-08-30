# ADR-002: Start With A Backend-First Skeleton

## Status

Accepted

## Context

CareerOps AI is meant to demonstrate backend engineering depth before AI feature breadth.

The target architecture separates a FastAPI API service, PostgreSQL as the system of record, Redis for cache/queue/rate-limit concerns, and a worker process for LLM calls.

Starting directly with AI workflows would make the project look like an LLM demo before the reliability surfaces are in place.

## Decision

Start with a small FastAPI backend skeleton, strict Python tooling, Docker Compose for PostgreSQL and Redis, and CI checks for linting, typing, import boundaries, and tests.

The first implemented endpoints are `GET /healthz` and `GET /readyz`. Business resources will be added in separate milestones so authentication, authorization, optimistic locking, idempotency, and database constraints can each be tested directly.

## Alternatives Considered

- Build the AI parsing flow first: faster visual progress, but it weakens the backend engineering story and delays the reliability foundation.
- Build the frontend first: useful for demos, but frontend is intentionally a smaller part of this project's recruiting signal.
- Build all infrastructure at once: risks a large unverified scaffold and makes it harder for the author to understand each layer.

## Consequences

This keeps the initial codebase easy to explain and gives every later feature a clear place to attach.

It also creates quality gates early: tests, strict typing, import-boundary checks, and dependency health checks exist before business complexity is added.

The trade-off is that the first milestone looks modest from a product perspective, but it is stronger as an engineering foundation.

## Verification Or Evidence

The skeleton currently includes health/readiness endpoints, Docker Compose services, strict project tooling, and CI configuration. The learning note in `docs/learning/0001-project-skeleton.md` records the verification performed for this milestone.

## Revisit If

Revisit only if the project goal changes from backend engineering depth to a rapid product prototype or frontend-first demo.
