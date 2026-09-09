# Groq Requirement Evaluation Summary - 2026-09-08

## Scope

Both runs used the same 12-case synthetic development dataset. The dataset has
31 labeled requirements and includes English, Chinese, bullets, negation,
irrelevant posting text, and instruction-like text.

These results measure this fixed development set only. They do not establish
production accuracy or independent holdout performance.

## Results

| Metric | parse-v1 | parse-v2 |
|---|---:|---:|
| Completed cases | 11 / 12 | 12 / 12 |
| Provider failures | 0 | 0 |
| Grounding/output failures | 1 | 0 |
| Text extraction precision | 100.00% | 100.00% |
| Text extraction recall | 90.32% | 100.00% |
| Text extraction F1 | 94.92% | 100.00% |
| Exact requirement F1 | 81.36% | 96.77% |
| Category accuracy on text matches | 100.00% | 96.77% |
| Skill accuracy on text matches | 85.71% | 100.00% |
| Exact case match rate | 58.33% | 91.67% |
| Input tokens | 4,094 | 5,686 |
| Output tokens | 1,533 | 1,781 |
| Mean completed-case latency | 636.27 ms | 643.58 ms |

Raw evidence:

- `2026-09-08-groq-requirement-eval-v1.json`
- `2026-09-08-groq-requirement-eval-v2.json`

## What Changed

`parse-v1` asked the model to copy exact source quotes. The Chinese case returned
corrupted copied text, which the grounding validator correctly rejected. Four
otherwise correct cases omitted an explicitly named technical skill inside a
responsibility.

`parse-v2` gives the model stable candidate IDs and lets application code restore
the original source text and spans. The prompt also explicitly applies skill
normalization to technologies named inside responsibilities.

## Remaining Error

The only v2 mismatch was:

```text
熟悉 Docker 更佳。
expected category: nice_to_have
predicted category: must_have
```

No v3 prompt was created for this single case. Further tuning on the same 12
examples would increase overfitting risk. Freeze `parse-v2` and evaluate a new
holdout set before changing the prompt again.

## Worker E2E Confirmation

After the v2 evaluation, one additional real worker test exercised FastAPI,
PostgreSQL, Redis, Dramatiq, Groq, validation, and the terminal database write.
The test passed, and the persisted row contained:

```text
model_name=openai/gpt-oss-20b
prompt_version=parse-v2
input_tokens=437
output_tokens=102
latency_ms=1052
status=succeeded
created_at=2026-09-09 06:53:10.374325+00
```

## Cost And Limitations

- v1 and v2 executed 24 evaluation cases and returned 13,094 measured tokens in
  total; HTTP request-attempt count was not measured because transient retries
  are internal to the adapter.
- One additional Chinese diagnostic request was made; its tokens were not saved.
- One additional parse-v2 worker E2E request used 539 measured tokens.
- Provider billing charge was not measured.
- The labels were authored by one person and were not independently reviewed.
- Exact-source-text scoring is intentionally strict.
- Latency values are not P50/P95 benchmarks.
