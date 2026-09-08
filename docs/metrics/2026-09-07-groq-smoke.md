# Groq Smoke Evidence - 2026-09-07

## Scope

This is compatibility evidence for `openai/gpt-oss-20b`, not a parser-quality,
cost, throughput, or reliability benchmark.

- Git base: `e37d719` plus the uncommitted Groq adapter working tree
- Provider endpoint: Groq OpenAI-compatible API
- Input: short synthetic internship JD; no resume, experience, or user data
- Attempts configured: at most 2 for transient failures

## Live Adapter Result

Command:

```powershell
$env:CAREEROPS_RUN_LLM_INTEGRATION='1'
.\.venv\Scripts\python -m pytest tests/integration/test_groq_live.py -q -s
```

Measured output:

```text
model=openai/gpt-oss-20b requirements=3 input_tokens=367 output_tokens=164 latency_ms=697
1 passed
```

## Real Worker E2E Result

Path exercised:

```text
FastAPI -> PostgreSQL queued row -> Redis -> Dramatiq worker
-> Groq -> grounding validation -> PostgreSQL succeeded row
```

The test passed. The persisted terminal row contained:

```text
model_name=openai/gpt-oss-20b
input_tokens=354
output_tokens=106
latency_ms=746
status=succeeded
created_at=2026-09-08 00:19:29.193843+00
```

The worker log recorded one `HTTP/1.1 200 OK` provider response for this run.

## Limitations

- Sample size: 2 synthetic requests.
- Provider billing charge: not measured.
- No labeled examples were scored, so precision, recall, and accuracy are not
  measured.
- Latency is from one local machine and is not a P50 or P95 claim.
- Free-tier limits and provider behavior may change.
