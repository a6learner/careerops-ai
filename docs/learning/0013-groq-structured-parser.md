# 0013 Groq Structured Requirement Parser

## What Changed

The worker can now select either the deterministic fake parser or a real Groq
parser. Groq receives an immutable JD snapshot and returns strict structured
requirements. The adapter turns exact source quotes into character spans and
captures provider-reported token usage.

## Why It Exists

The real provider demonstrates that the worker boundary handles network latency,
rate limits, malformed output, and external failures without coupling those
concerns to FastAPI or the database repository.

The fake remains essential. Most correctness tests should prove our code, not
depend on a changing model, network access, quota, or money.

## Failure Modes It Prevents

- CI unexpectedly calling a paid or rate-limited provider.
- A missing API key failing only after a task has already started.
- Retrying permanent authentication or request-shape errors.
- Unlimited retries consuming quota after a provider outage.
- Persisting model text that cannot be found in the submitted JD.
- Trusting model-generated character offsets.
- Accidentally committing a local API key.

## How To Verify It

Run all offline checks; these use the fake or an HTTP mock:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
```

Run the one-request live adapter test only when intentionally spending quota:

```powershell
$env:CAREEROPS_RUN_LLM_INTEGRATION='1'
.\.venv\Scripts\python -m pytest tests/integration/test_groq_live.py -s
Remove-Item Env:CAREEROPS_RUN_LLM_INTEGRATION
```

The local `.env` selects `groq`; `.env.example` deliberately defaults to `fake`
so a fresh checkout cannot make an accidental provider request.

## What You Must Understand

Level 1: JSON Schema guarantees shape, not truth. The database may persist a
positive requirement only after programmatic source grounding succeeds.

Level 1: Retries trade availability against duplicate cost. This adapter retries
only transient transport/server failures and caps attempts at two. A request may
have reached the provider even when the client did not receive its response.

Level 1: Provider usage tests and deterministic regression tests serve different
purposes. Live tests prove compatibility; labeled fixtures are needed to measure
quality.

Level 2: `SecretStr` reduces accidental display but does not replace environment
isolation. The API key remains outside Git and should be available only to the
worker in deployment.

Level 2: The model returns exact quotes rather than offsets. The adapter finds
the quote in the original Python string, resolves repeated occurrences, and lets
the execution service validate the resulting span again.

## Knowledge Check

1. Why does strict JSON Schema not eliminate the grounding validator?
2. Why are HTTP 401 and invalid model output not retried?
3. What duplicate-cost window still exists when a network request times out?
4. Why does `.env.example` use `fake` even though local `.env` uses `groq`?
5. Why are two successful synthetic requests insufficient to claim parser accuracy?
