# CareerOps AI Project Context

CareerOps AI is a portfolio-grade backend project for a CS master's student preparing for 2027 Summer software engineering, backend, and AI engineering internships.

The project has three purposes, in priority order:

1. Become a backend project strong enough to put on a resume and discuss deeply in interviews.
2. Help the author practice the full backend development loop: requirements, design, implementation, tests, deployment, observability, and review.
3. Solve a real personal workflow: matching job descriptions to verified personal experiences.

The recruiting signal target is approximately:

| Area | Weight |
|---|---:|
| Backend and systems engineering | 65% |
| AI engineering | 25% |
| Frontend | 10% |

When trade-offs conflict, prefer the choice that better demonstrates backend engineering judgment.

## Product Positioning

CareerOps AI is not intended to be a general AI assistant, a thin LLM wrapper, or a portfolio stuffed with features.

The core claim is:

> A reliable backend service with explicit concurrency control, transaction boundaries, idempotency, caching, observability, and a safe boundary around an unreliable AI dependency.

The interview story should be about system design, data integrity, failure handling, and measurable behavior. The LLM is part of the system, but it is not the system.

## User

The MVP serves one user type: a CS student applying to SWE / backend / AI internships in the United States.

This user tracks multiple jobs, owns a set of project/course/work experiences, and needs help connecting each job requirement to real evidence from those experiences.

The MVP does not serve recruiters, teams, or enterprise hiring workflows.

## Core Loop

The MVP is successful only when this flow works end to end:

```text
register/login -> build experience library -> save job description
-> parse structured requirements -> match requirements to real evidence
-> review evidence and gaps -> create tasks -> track application status
-> view progress in a dashboard
```

## Product Integrity Principle

The system must never say the user has a skill or experience without evidence.

If evidence is missing, the system should explicitly represent that as a gap or insufficient evidence. This is both an ethical product requirement and the project's strongest engineering idea.

## Author Learning Context

The author already has experience with Python, MySQL, a complete RAG workflow, and OpenAI-compatible APIs.

The author has used but wants more practice with FastAPI, Docker, and pytest.

The project should deliberately build skill in PostgreSQL, Redis, worker queues, cloud deployment, and React/Next.js. When those technologies appear for the first time, Codex should explain the engineering reason and failure mode, not just add code.

## Time And Scope

The intended development budget is about 8-10 effective development weeks, with roughly 12 hours per week.

The project should freeze feature work around the seventh effective development week. After that, prioritize tests, deployment, docs, demo quality, metrics, and interview preparation.

If schedule pressure appears, cut scope before cutting tests, deployment, or evidence guarantees.

## Source Material

- Detailed MVP scope: `docs/CareerOps AI MVP 产品范围与 Non-goals.md`
- User stories and use cases: `docs/product/user-stories-and-use-cases.md`
- Programming language research: `docs/52 条 2027 届实习 JD 语言要求调研.md`
- Decision records: `docs/decisions/`
- Learning notes: `docs/learning/`
- Measured evidence: `docs/metrics/`
