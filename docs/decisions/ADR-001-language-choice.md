# ADR-001: Use Python For The MVP Backend

## Status

Accepted

## Context

CareerOps AI is a backend systems project with a constrained LLM integration, not a Java/Spring portfolio project and not a model demo.

The author researched 52 real 2027 internship and new-grad job descriptions in August 2026. Python appeared more often than Java in the collected sample, especially across AI/ML, data, platform automation, and security-oriented roles. Large-company general SWE internships generally asked for one general-purpose programming language rather than a specific Java requirement.

The full evidence is stored in `docs/52 条 2027 届实习 JD 语言要求调研.md`.

## Decision

Use Python 3.11+ as the primary backend language for the MVP.

Python must be written with explicit engineering discipline:

- `mypy --strict`
- Pydantic or dataclass contracts across layers
- clear API/service/repository boundaries
- database constraints for persisted invariants
- pytest coverage for behavior, failure paths, authorization, concurrency, and LLM-adjacent logic

The decision is not "Python because it is easy." The decision is "Python because it fits the AI/backend boundary of this MVP, while strict typing and database-backed invariants preserve backend engineering signal."

## Alternatives Considered

- Java + Spring Boot: strong enterprise backend signal, but it would consume more of the 8-10 week MVP budget and move attention away from evidence validation, async workflows, testing, observability, and evaluation.
- TypeScript full stack: good product velocity and Next.js alignment, but weaker for the author's current AI/backend learning goal and less useful for PostgreSQL/worker-focused practice in this project.
- Polyglot backend: unnecessary complexity for an interview portfolio MVP.

## Consequences

The project can move quickly through API, worker, LLM adapter, evaluation, and test infrastructure.

The main risk is that Python projects can look informal if quality gates are weak. This is addressed through strict typing, import-boundary checks, database constraints, deterministic tests, and measured outputs.

## Verification Or Evidence

The language choice is supported by the saved JD research file and by the project's backend-plus-LLM scope. The quality of the decision should be judged by the repository's checks, tests, constraints, and demo behavior, not by language popularity alone.

## Revisit If

Reconsider this decision only if the project goal changes toward JVM enterprise backend roles, Android/backend roles, low-latency trading, or a job target that explicitly requires Java/Spring evidence.
