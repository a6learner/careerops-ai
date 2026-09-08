# ADR-012: Groq Requirement Parser

## Status

Accepted

## Context

ADR-011 introduced a worker-side `RequirementParser` boundary and a deterministic
fake. The project now needs one real provider to demonstrate unreliable external
dependency handling without making CI nondeterministic or expensive.

The parser must return structured requirements grounded in an immutable JD
snapshot. Asking a language model to calculate Python character offsets is
unreliable, especially with repeated text or Unicode.

## Decision

Use Groq's OpenAI-compatible Chat Completions endpoint with
`openai/gpt-oss-20b`. Call it through `httpx` behind the existing
`RequirementParser` protocol. The API service still only dispatches parse-run
IDs; only the worker constructs and calls the configured parser.

`fake` remains the default provider. Unit tests and CI do not access a network.
Selecting `groq` requires `CAREEROPS_LLM_API_KEY`; the key stays in the ignored
`.env` file and is passed only to the worker container in local Compose.

The request uses strict JSON Schema. The provider returns each category, an
exact contiguous quote from the JD, and an optional normalized skill. Application
code locates distinct occurrences of those quotes and calculates source spans.
The existing execution validator then independently verifies every span before
requirements can be persisted.

Each call has a 30-second timeout and at most two attempts by default. Only
network failures, HTTP 429, and selected HTTP 5xx responses are retried. HTTP
4xx configuration/authentication failures and invalid structured output are not
retried. Dramatiq transport retries remain disabled.

The worker records provider-reported input/output token counts and the measured
execution latency on the parse run. These fields are evidence; they are not a
quality or cost claim.

## Alternatives Considered

- OpenRouter: useful future fallback and model-routing layer, but its free router
  may select different models and is less reproducible for the first evaluation.
- Gemini free tier: inexpensive, but adds a different provider contract while
  Groq already exposes the OpenAI-compatible boundary selected for portability.
- Groq SDK: rejected for now because direct `httpx` needs one existing runtime
  dependency and keeps provider response validation explicit.
- Model-generated character offsets: rejected because exact quotes plus
  programmatic span resolution are easier to validate and explain.
- Retry every failure: rejected because authentication, schema, and grounding
  failures do not become correct through blind retries and can waste quota.

## Consequences

Provider selection is configuration-only at the worker boundary. Switching to
another OpenAI-compatible endpoint will still require compatibility tests, but
not a change to the execution service contract.

Strict schema compliance does not prove semantic correctness. Exact-quote
grounding and the existing programmatic validator remain necessary. Repeated
identical quotes are assigned to distinct source occurrences; an unquoted model
claim fails the run with `PARSER_OUTPUT_INVALID`.

The free-tier rate limit can reject large or bursty workloads. The MVP uses the
fake for automated tests and explicitly enabled, small synthetic inputs for live
verification.

## Verification Or Evidence

- Mock-transport tests cover strict schema requests, grounded spans, repeated
  quotes, transient retry, permanent HTTP failure, and unsupported claims.
- Factory tests prove fake-by-default behavior and fail-fast Groq key handling.
- An explicitly enabled live adapter test and a real worker E2E both succeeded.
- Raw measured token and latency evidence is saved in
  `docs/metrics/2026-09-07-groq-smoke.md`.
- `mypy --strict`, Ruff, import-linter, and the default pytest suite must pass
  without a real provider call.

## Revisit If

Revisit after a labeled JD evaluation, if Groq free-tier availability is
insufficient, if a second provider is required, or if measured failures justify
a different retry or model policy.
