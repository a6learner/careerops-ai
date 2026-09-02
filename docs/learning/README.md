# CareerOps AI Learning Notes

This directory records what changed, why it matters, what the author must understand, and how the topic may appear in interviews.

Keep implementation explanations here instead of filling code with tutorial comments. Code should stay clean; learning material should stay searchable.

## Understanding Levels

Use these levels when writing task summaries and learning notes.

### Level 1 - Must Explain In Interviews

The author must be able to explain the design, failure modes, and trade-offs:

- architecture
- data model
- API contracts
- authentication and authorization
- transactions
- concurrency control
- idempotency
- caching
- queues and retries
- rate limits
- LLM adapter boundaries
- evidence validation
- database constraints
- observability
- testing strategy
- deployment
- measured results

### Level 2 - Should Understand Well Enough To Modify

The author should be able to read and safely change:

- FastAPI routes and dependencies
- Pydantic models
- SQLAlchemy and Alembic usage
- Redis commands and data shapes
- worker configuration
- Docker Compose services
- CI checks
- structured logging
- error handling

### Level 3 - Need Not Memorize Line By Line

The author should know what these do, but does not need to memorize syntax:

- routine framework boilerplate
- simple CRUD wiring
- generated migration scaffolding
- GitHub Actions YAML details
- basic frontend styling

## Note Template

Each important feature or infrastructure step should add or update a short note with:

```markdown
# NNNN Topic

## What Changed

## Why It Exists

## Failure Modes It Prevents

## How To Verify It

## What You Must Understand

## Knowledge Check

1. Question that tests the key concept.
2. Question about a failure mode.
3. Question about a trade-off or alternative.
```

Knowledge Check questions should not immediately turn into long answers. They are prompts for the author to practice explaining the system.

## Current Documents

- [0001 Project Skeleton](0001-project-skeleton.md)
- [0002 Database Migrations And The Users Table](0002-database-migrations.md)
- [0003 Local Environment Isolation](0003-local-environment-isolation.md)
- [0004 Password Hashing](0004-password-hashing.md)
- [0005 Line Endings](0005-line-endings.md)
- [0006 Registration API](0006-register-api.md)
- [0007 Login And Access Tokens](0007-login-and-access-tokens.md)
