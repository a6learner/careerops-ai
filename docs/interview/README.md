# Interview Preparation

This directory turns implementation work into interview material.

The goal is not to memorize the repository. The goal is to explain the important engineering decisions, failure modes, trade-offs, and measured results clearly.

## What To Capture

For each completed milestone, capture:

- the problem solved
- the design chosen
- alternatives considered
- the failure mode the design prevents
- tests or metrics that prove the behavior
- one concise interview story
- likely follow-up questions

## Question Levels

Use these levels to prepare:

| Level | Focus |
|---|---|
| 1 | Basic concepts, such as what RAG, transactions, or idempotency mean |
| 2 | Project-specific design, such as why the API does not call the LLM directly |
| 3 | Engineering depth, such as race conditions, rollback behavior, or cache invalidation |
| 4 | Scaling and operations, such as how the system changes at 10x or 100x traffic |
| 5 | Challenge questions, such as why not use a graph database, microservices, or a direct LLM call |

## No Fake Stories

Every resume bullet or interview claim that includes a number must link back to `docs/metrics/` or a committed test/evaluation artifact.

If the project has not measured something yet, describe the design honestly and say the measurement is pending.
