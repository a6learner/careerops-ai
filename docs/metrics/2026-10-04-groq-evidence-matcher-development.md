# Groq Evidence Matcher Development Run - 2026-10-04

## Scope

This is the first authorized real-provider matcher development run. It uses only
project-author-reviewed synthetic inputs. It does not change production Analysis
Runs, evaluate the matcher holdout, or establish production accuracy.

- Git state: `6041cf378004dc65c2634c666194a61465a565ab` plus the P1-5c working tree
- Provider: Groq
- Model: `openai/gpt-oss-20b`
- Schema: `evidence-matcher-schema-v1`
- Prompt: `evidence-matcher-prompt-v1`
- Development cases: 12
- Provider attempt budget / used: 12 / 12
- Per-case attempts: 1; retries: 0
- Maximum output tokens per request: 800
- Real resume or Job data: 0
- Holdout provider attempts: 0
- Corpus SHA-256: `139729a73aa99dc6cd6a9199d8c1b44e901e3d4cb1171ef4abd4990071fd1d0f`
- Development-case SHA-256: `3c43b7d472270bcedaba3397abeea18a05ec3b781c32a4ed2521f9c396d58efa`

The immutable case-level report is stored in
`2026-10-04-groq-evidence-matcher-development.json`.

## Observed Result

| Metric | Result |
|---|---:|
| Completed cases | 6 / 12 |
| Provider failures | 6 |
| Rate-limited cases | 6 |
| Output failures | 0 |
| Schema pass rate | 0.5000 |
| Completed positive citations valid | 4 / 4 |
| Unsupported positive claim rate | 0.0000 |
| Input tokens reported | 6,567 |
| Output tokens reported | 1,081 |
| Mean completed-case matcher latency | 729.5 ms |

The remaining six cases were all classified as `provider_rate_limited`. Because
only half the dataset completed, verdict accuracy, macro-F1, exact-match, gap, and
confidence scores are partial diagnostics and must not be used as complete model
quality evidence.

## Confirmed Rate-Limit Cause

The runner sent requests in about nine seconds. The first six completed cases
reported 6,567 input plus 1,081 output tokens, or 7,648 tokens. Request seven then
entered the same rolling one-minute window and pushed usage beyond the model's 8K
TPM allowance; cases 7 through 12 received 429 responses. The Groq console showed
about 8.2K tokens for the day, which is far below the 200K TPD allowance. This is
evidence of a short-time-window throughput spike, not daily or monthly exhaustion.

The console total is a provider UI observation supplied by the project author;
the immutable JSON report is authoritative for the 7,648 provider-reported tokens
from successful cases and the six `provider_rate_limited` case outcomes.

Among completed cases, the model selected the correct verdict for both `matched`
and both `partial` cases and swapped the two gap categories. Its positive quotes
were grounded but did not exactly equal the single frozen gold quote, so strict
positive-evidence exact accuracy was zero. That distinction shows why citation
validity and exact-gold matching are separate metrics.

## Cost Interpretation

Provider billing was not measured. Using Groq's published 2026-10-04 list prices
for this model ($0.075 per million input tokens and $0.30 per million output
tokens), the reported completed-token usage corresponds to an estimated $0.00082.
This estimate excludes failed-request accounting and must not be presented as a
billed amount or stable future price.

## Recovery Boundary

Do not overwrite or relabel this report. The offline-tested recovery path requires
new explicit authorization and a new output artifact. It uses this report via
`--resume-from`, enforces a six-attempt ceiling, spaces calls by at least 11
seconds, covers only `matcher-dev-007` through `matcher-dev-012`, and merges by case
ID without recalling the six successful cases. Holdout remains sealed.

The separately authorized recovery completed all six failed cases and is recorded
in `2026-10-04-groq-evidence-matcher-development-recovery.md` and its corresponding
JSON report. This partial artifact remains authoritative evidence of the original
TPM failure.

## Verification

```text
Focused P1-5 and Groq parser tests: 76 passed
Strict mypy: no issues in 111 source files
Ruff: all checks passed
Import contracts: 2 kept, 0 broken
```

Mock-provider tests cover the live runner's opt-in, budget, output immutability,
failure mapping, paced recovery of only failed cases, prior-result preservation,
and pre-provider holdout refusal. Post-run inspection confirmed 12 development
attempts, six durable rate-limit failures, and no holdout case IDs in the report.

## Limitations

- Half of the development cases did not complete.
- Inputs and labels are synthetic and single-reviewer.
- Provider behavior and rate limits can change under the same model name.
- Candidate lists are frozen matcher inputs, not retrieval-quality evidence.
- Latency excludes API, queue, database, and worker time.
- No conclusion about holdout or production quality is supported.
