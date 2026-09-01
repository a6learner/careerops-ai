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
