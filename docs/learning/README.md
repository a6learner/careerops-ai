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
- [0008 Current User Dependency](0008-current-user-dependency.md)
- [0009 Experiences CRUD And Object-Level Authorization](0009-experiences-crud-and-authorization.md)
- [0010 Jobs CRUD And Cursor Pagination](0010-jobs-crud-and-pagination.md)
- [0011 Parse Runs And Job Requirements](0011-parse-runs-and-job-requirements.md)
- [0012 Worker-Backed Parse Execution](0012-worker-backed-parse-execution.md)
- [0013 Groq Structured Requirement Parser](0013-groq-structured-parser.md)
- [0014 Requirement Parser Evaluation](0014-parser-evaluation.md)
- [0015 Evidence Integrity Foundation](0015-evidence-integrity-foundation.md)
- [0016 Analysis Run End-To-End](0016-analysis-run-end-to-end.md)
- [0017 Action Items](0017-action-items.md)
- [0018 Dashboard Aggregation And Cache](0018-dashboard-aggregation-and-cache.md)
- [0019 Experience Embedding Lifecycle](0019-experience-embedding-lifecycle.md)
- [0020 Evidence Retrieval Evaluation Baseline](0020-retrieval-evaluation-baseline.md)
- [0021 Retrieval Evaluation V2](0021-retrieval-evaluation-v2.md)
- [0022 Real Embedding Evaluation](0022-real-embedding-evaluation.md)
- [0023 Frozen Embedding Holdout](0023-frozen-embedding-holdout.md)
- [0024 Local Exact Hybrid Retrieval](0024-local-hybrid-retrieval.md)
- [0025 Offline Real Evidence Matcher Contract](0025-offline-real-evidence-matcher-contract.md)
- [0026 Evidence Matcher Evaluation V1](0026-evidence-matcher-evaluation-v1.md)
- [0027 Groq Evidence Matcher Development Integration](0027-groq-evidence-matcher-development.md)
- [0028 Evidence Matcher Evaluation Rubric V2](0028-evidence-matcher-evaluation-rubric-v2.md)
- [0029 Evidence Matcher Coverage Evaluation](0029-evidence-matcher-coverage-evaluation.md)
- [0030 Evidence Matcher Development Stop](0030-evidence-matcher-development-stop.md)
- [0031 One-Time Evidence Matcher Holdout](0031-one-time-evidence-matcher-holdout.md)
- [0032 Real Evidence Matcher Worker Integration](0032-real-evidence-matcher-worker-integration.md)
- [0033 Analysis Admission Rate Limiting](0033-analysis-admission-rate-limiting.md)
- [0034 Analysis Run Observability](0034-analysis-run-observability.md)
- [0035 Analysis Run Lifecycle Constraint](0035-analysis-run-lifecycle-constraint.md)
