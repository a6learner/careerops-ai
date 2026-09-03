# AGENTS.md - CareerOps AI

This file is the operating manual for Codex. Keep it short, actionable, and focused on how to work in this repository.

## Mission

CareerOps AI is an interview-oriented backend engineering project for 2027 Summer SWE / backend / AI engineering internships.

The project must show that the author can design, test, explain, and operate a reliable backend system that safely integrates an unreliable AI dependency. Product value comes from engineering reliability, not from model cleverness.

When trade-offs conflict, optimize for backend and systems engineering signal first, AI engineering second, frontend polish third.

Reference material lives in:

- `docs/PROJECT_CONTEXT.md` for project background and positioning.
- `docs/CareerOps AI MVP 产品范围与 Non-goals.md` for detailed product scope.
- `docs/decisions/` for decision records.
- `docs/learning/` for implementation explanations and knowledge checks.
- `docs/metrics/` for measured evidence used in resumes or claims.

## Hard Constraints

These are architectural constraints. Do not change them without explicit author approval.

1. API service must never call the LLM directly. Model calls happen behind worker-side workflow boundaries so API latency remains predictable and tests can stay deterministic.
2. PostgreSQL is the system of record. Redis data must be disposable and rebuildable.
3. LLM access must go through an adapter interface. CI must be able to use a fake provider with fixed responses, no network, and no cost.
4. Use a monolithic API plus an independent worker. Do not split into microservices without a real scale or ownership need.
5. The system must never claim the user has a skill or experience without traceable evidence.
6. Evidence validation must have three layers: schema validation, programmatic validation, and database constraints.

## Current Project Decisions

These decisions are accepted for the current MVP. Do not proactively replace them. If a serious implementation problem appears, propose or update an ADR instead of silently changing direction.

| Area | Decision |
|---|---|
| Language | Python 3.11+ |
| Type checking | `mypy --strict` |
| API | FastAPI |
| Database | PostgreSQL with pgvector |
| Cache / queue / rate limit | Redis |
| Migrations | Alembic |
| Tests | pytest |
| Containers | Docker + Compose |
| CI | GitHub Actions |
| Frontend | Next.js as a demo layer |

Codex may choose implementation details inside these boundaries: ORM usage, Pydantic model organization, dependency injection style, worker library, authentication mechanism, retrieval approach, frontend state management, deployment target, and import-boundary tooling.

Record meaningful choices in `docs/decisions/`.

## Stop Conditions

Stop and ask the author before doing any of these:

- Changing a hard constraint.
- Adding a major dependency, external service, paid API, or new infrastructure component.
- Changing database semantics, migrations, authorization behavior, or public API contracts.
- Weakening validation, authorization, type checks, import-boundary checks, tests, or evidence guarantees.
- Skipping, deleting, or loosening failing tests to make a check pass.
- Resolving ambiguous product behavior by assumption when the choice affects user data or resume claims.
- Deleting significant code, rewriting a module wholesale, or doing a cross-module refactor that was not requested.
- Introducing generated metrics, benchmark claims, or resume bullets that are not backed by saved evidence.

## Autonomous vs Confirmation

Codex may act autonomously for small, reversible work that fits existing patterns:

- Typos, formatting, small documentation updates.
- Focused bug fixes with clear expected behavior.
- Test repairs that preserve the original intent.
- Lint, typing, or import-boundary fixes.
- Small refactors inside one module.
- Updating learning notes after an implemented task.

Ask before larger or irreversible work:

- New features, schemas, migrations, dependencies, services, deployment changes, authentication changes, API contract changes, or architectural decisions.
- Any change that affects data ownership, user privacy, authorization, evidence integrity, or metrics.

When in doubt, explain the trade-off and ask.

## Engineering Discipline

These requirements are not optional:

1. `mypy --strict` must pass. Do not use `# type: ignore` as a shortcut. Use explicit `cast` only at third-party boundaries and explain why.
2. Do not pass bare `dict` across layer boundaries. Use Pydantic models or dataclasses for API, service, repository, and LLM adapter contracts.
3. `Optional` must mean a real business possibility, not unhandled uncertainty.
4. Keep dependencies one-way: API -> service -> repository. Service code must not import FastAPI objects. Repository code must not import service code.
5. Put database invariants in DDL with CHECK, UNIQUE, foreign key, exclusion, or partial-index constraints when the invariant belongs to persisted data.
6. Keep functions small and names explicit. Prefer clear structure over explanatory comments.
7. Write comments only for why something non-obvious exists, not for what the next line does.
8. Do not add abstraction for future possibilities unless there is a real second implementation or a testing boundary. The LLM adapter is an intentional exception.

## Product Guardrails

MVP serves one user type: a CS student applying to SWE / backend / AI internships.

The core loop is:

```text
register/login -> build experience library -> save job description
-> parse structured requirements -> match requirements to real evidence
-> review evidence and gaps -> create tasks -> track application status
-> view progress in a dashboard
```

Do not add automatic applications, job scraping, resume layout generation, multi-agent autonomy, team collaboration, enterprise ATS features, email/calendar integration, mobile apps, real-time collaboration, model fine-tuning, graph databases, a single "match percentage" score, or microservices.

For a proposed feature, ask: can the user still complete the core loop without it? If yes, it is not P0.

## Evidence Protection

Treat evidence matching as the technical center of the project.

1. Schema layer: model output must match the expected schema. Invalid shape is an upstream failure.
2. Validation layer: code must verify that cited experiences exist, belong to the current user, and contain the cited text or span.
3. Database layer: constraints must prevent unsupported positive claims from being persisted even if application code has a bug.

No positive skill or experience claim may be stored or shown without traceable evidence. Missing evidence must be represented as a gap or insufficient evidence.

## No Fake Metrics

Never invent benchmark results, latency improvements, accuracy, recall, throughput, cost savings, coverage, reliability, cache hit rate, or task success rate.

If something was not measured, say `not measured`.

Any number used in README, docs, resume bullets, demo scripts, or interview notes must point to a saved artifact under `docs/metrics/` or an equivalent committed test/evaluation output.

## Work Style

Before substantive code changes, briefly explain:

- What will change.
- Why this is the right slice.
- Which files are likely involved.
- How it will be verified.

Do not make huge multi-module changes in one pass. Prefer small, independently testable steps.

After each task, provide:

- What changed.
- Key decisions and trade-offs.
- Verification performed.
- What the author should understand.
- A short Knowledge Check when the task introduced important engineering concepts.

## Long-Running Thread Hygiene

Treat chat as a temporary workspace, not the source of truth. Durable project
memory must live in repository files and Git history.

Proactively suggest starting a fresh development thread when a major module or
milestone is complete, when the conversation has become long enough that old
plans and completed work are easy to confuse, or before switching to a new theme
such as auth, experiences, jobs, workers, LLM integration, evidence matching,
frontend, deployment, or interview prep.

Before suggesting a fresh thread, make sure important context has been saved in
the appropriate place:

- Design decisions in `docs/decisions/`.
- Learning notes in `docs/learning/`.
- Real measurements in `docs/metrics/`.
- Run and setup instructions in `README.md`.
- Code history in clear Git commits.

When a fresh thread starts, first read `AGENTS.md`, `docs/PROJECT_CONTEXT.md`,
`docs/decisions/`, `docs/learning/`, and `README.md`, then summarize current
project state and recommend the next step before changing code.

## Understanding Levels

The author does not need to memorize every generated line. The author must be able to explain the important engineering behavior.

Level 1 - Must explain in interviews:

- Architecture, data model, API contracts, authentication, authorization, transactions, concurrency, idempotency, caching, queues, rate limits, LLM adapter boundaries, evidence validation, database constraints, observability, testing strategy, deployment, and measured results.

Level 2 - Should understand well enough to modify:

- FastAPI routing and dependencies, Pydantic models, SQLAlchemy/Alembic usage, Redis commands, worker configuration, Docker Compose, CI checks, structured logging, and error handling.

Level 3 - Need not memorize line by line:

- Routine boilerplate, simple CRUD wiring, framework configuration syntax, generated migration scaffolding, GitHub Actions YAML details, and basic frontend styling.

When delivering code, identify which Level 1 or Level 2 concepts were introduced or changed.

## Knowledge Check

For every important feature or infrastructure step, update or create a short document under `docs/learning/`.

Each learning note should include:

- What changed.
- Why it exists.
- Failure modes it prevents.
- How it was verified.
- What the author must understand.
- Knowledge Check questions.

Knowledge Check questions should test understanding without immediately giving long answers. They should be specific enough that the author can answer from the code and docs.

## ADR / Decision Policy

Create or update a decision record when a change affects architecture, dependencies, data model, concurrency, queueing, caching, authorization, deployment, LLM provider boundaries, evaluation strategy, or measurable resume claims.

Use this shape:

- Title
- Status
- Context
- Decision
- Alternatives considered
- Consequences
- Verification or evidence

Small implementation choices can be explained in the task summary. Durable decisions belong in `docs/decisions/`.

## Testing Definition Of Done

A feature is not done until:

- It works and has relevant tests.
- Failure paths are handled.
- `mypy --strict`, linting, import-boundary checks, and tests pass in the intended local/CI workflow.
- Concurrency, transactions, idempotency, and authorization have direct tests when affected.
- LLM-related tests use a fake provider.
- Related README, ADR, learning, or metric docs are updated.
- The author can explain the Level 1 and Level 2 concepts touched by the change.

Testing should be layered:

| Layer | Purpose |
|---|---|
| Unit | Validation logic, state machines, rate-limit algorithms |
| Integration | API with real PostgreSQL container |
| Authorization | Cross-user access matrix for each resource |
| Concurrency | Duplicate analysis and concurrent record updates |
| AI regression | Fixed labeled examples with deterministic fake provider |
| Load | Main read endpoints with saved P50/P95 evidence |

## Commit And Documentation Style

Use English commit messages that say what changed and why. Avoid vague messages like `update`, `fix`, or `1`.

Write docs in plain language. Do not add decorative badges or filler. Keep code comments sparse and useful.
