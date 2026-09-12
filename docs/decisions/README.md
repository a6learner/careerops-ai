# Decision Records

This directory records durable engineering decisions for CareerOps AI.

Use a decision record when a choice affects architecture, dependencies, data model, concurrency, queueing, caching, authorization, deployment, LLM provider boundaries, evaluation strategy, or resume-worthy metrics.

Small local implementation choices can stay in the task summary. Decisions that future work must preserve or understand belong here.

## Policy

Before changing an accepted decision, create a new ADR or update the existing one with the reason for reconsideration. Do not silently replace a current project decision because a different tool or framework is fashionable.

Each record should answer:

- What problem are we solving?
- What did we choose?
- What alternatives did we consider?
- What trade-offs did we accept?
- How will we verify that the decision works?
- What would make us revisit it?

## Template

```markdown
# ADR-NNN: Title

## Status

Proposed | Accepted | Superseded

## Context

What situation forced this decision?

## Decision

What are we choosing?

## Alternatives Considered

- Option A: why not
- Option B: why not

## Consequences

What becomes easier, harder, or riskier?

## Verification Or Evidence

What test, metric, benchmark, demo, or source supports this decision?

## Revisit If

What future condition would justify reopening this decision?
```

## Current Records

- `ADR-001-language-choice.md`: Python as the primary implementation language.
- `ADR-002-backend-first-skeleton.md`: backend-first skeleton before AI workflow implementation.
- `ADR-003-database-migrations-and-users.md`: Alembic migrations and the first `users` table.
- `ADR-004-password-hashing.md`: Argon2id password hashing behind a local security boundary.
- `ADR-005-registration-layering.md`: registration through API, service, and repository layers.
- `ADR-006-access-token-auth.md`: signed JWT access tokens for login.
- `ADR-007-current-user-dependency.md`: reusable current-user dependency for protected endpoints.
- `ADR-008-experiences-crud-and-authorization.md`: experiences CRUD with object-level authorization, soft deletion, optimistic locking, and pgvector storage.
- `ADR-009-jobs-resource-and-pagination.md`: jobs CRUD with object-level authorization, soft deletion, optimistic locking, status filtering, and cursor pagination.
- `ADR-010-parse-runs-and-job-requirements.md`: parse run resources and structured job requirements with idempotent submission and source spans.
- `ADR-011-worker-backed-parse-execution.md`: asynchronous parse execution with Dramatiq, PostgreSQL state transitions, input snapshots, and recovery.
- `ADR-012-groq-requirement-parser.md`: Groq structured output behind the worker parser boundary with bounded transient retries and candidate-ID grounding.
- `ADR-013-requirement-parser-evaluation.md`: versioned labeled datasets, separated quality metrics, immutable raw evidence, and development-versus-holdout discipline.
- `ADR-014-evidence-integrity-foundation.md`: analysis result persistence, semantic citation validation, structural database constraints, and atomic completion.
- `ADR-015-analysis-run-end-to-end.md`: Analysis Run API, deterministic retrieval, fake matching, worker lifecycle, recovery, and complete verdict enforcement.
