# Provider probes during large_scale_v1 (2026-11-01, local time UTC-8)

These are one-off diagnostic requests made by the orchestrator during the run, outside the product, to explain
failures. Each sends the product's exact parser payload (system prompt from `requirement_parser_instructions()`,
candidates from `extract_source_candidates()`, the strict `job_requirements` JSON schema, `reasoning_effort: low`,
`temperature: 0.1`, `max_completion_tokens: 1500`) or a matcher-shaped request using
`groq_matcher_response_json_schema()`. The probe script is `provider_probe.py.txt` in this folder. API keys were
read from `.env` and never printed. Outputs below are copied from the probe output; organization IDs are redacted.

## Groq free tier, direct (about 14:29–15:40)

| Probe | Result |
|---|---|
| 1-token request | HTTP 200; headers `x-ratelimit-limit-requests: 1000` (per day), `x-ratelimit-limit-tokens: 8000` (per minute) |
| Parser payload, `jd-3121834c33` (4 candidates) | HTTP 400 `json_validate_failed`: "jsonschema: '/requirements' does not validate with /properties/requirements/minItems: minItems: got 0, want 1"; `failed_generation` was `{"requirements":[] }` |
| Parser payload, `jd-5f93b2b3be` (455 candidates) | HTTP 413: "Request too large for model `openai/gpt-oss-20b` … on tokens per minute (TPM): Limit 8000, Requested 10853" |
| Parser payload, `jd-26eec39d7f` and `jd-0b79ce35f2` | HTTP 200 (2,521 and 2,140 prompt tokens); their earlier `PARSER_FAILED` runs were therefore not deterministic |

## OpenRouter, upstream not pinned (about 18:10–19:45)

| Probe | Result |
|---|---|
| Parser payload, `jd-26eec39d7f` | HTTP 200, about $0.00016 per request |
| Parser payload, `jd-3121834c33` | HTTP 200 (the JD that Groq rejected with HTTP 400) |
| Same parser payload for `jd-26eec39d7f`, 4 times | upstreams DekaLLM, Darkbloom, AkashML, Parasail; completion tokens 200, 384, 832, 558; reasoning tokens 174, 77, 0, 165 |

## OpenRouter, Allowed Providers = Groq (from about 19:50)

| Probe | Result |
|---|---|
| Same parser payload for `jd-26eec39d7f`, 3 times | upstream Groq each time; completion tokens 1133, 1181, 284 |
| Matcher-shaped request (25 requirements, no experiences), `max_completion_tokens` 60 and 800 | HTTP 200 both times; `finish_reason: "error"`, `message.content: null`, error `{"code": 502, "message": "Upstream error from Groq: Parsing failed. The model generated output that could not be parsed. …"}` |

## How the product maps these responses (source code, unchanged)

- `src/careerops/adapters/groq_chat.py` `classify_groq_status`: HTTP 400 and 413 → `REQUEST_FAILED`; 429 →
  `RATE_LIMITED`.
- `src/careerops/adapters/groq_evidence_matcher.py`: `_MessagePayload.content` is a required `str`, so a 200
  response with `content: null` fails envelope validation and raises `REQUEST_FAILED`.
- `src/careerops/services/analysis_run_execution.py`: matcher `REQUEST_FAILED` → `MATCHER_PROVIDER_FAILED`.
- `src/careerops/adapters/evidence_matcher_factory.py`: `GROQ_EVIDENCE_MATCHER_MAX_OUTPUT_TOKENS = 800`.

## Run configuration not stored elsewhere

- Fake-provider scale stack worker: `dramatiq careerops.workers.tasks --processes 2 --threads 4`.
- Real-run worker: `--processes 1 --threads 4`.
