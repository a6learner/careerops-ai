# Groq Evidence Matcher Prompt V3-V5 Development Record

## Scope

This record compares three bounded Groq development runs using the unchanged
synthetic corpus and development labels. Each run used 12 single-attempt requests,
at least 11 seconds between request starts, `openai/gpt-oss-20b`, low reasoning,
temperature 0, and an 800-token completion ceiling. No matcher holdout file was
read or called, and retrieval parameters did not change.

The three runs made 36 requests. All completed without provider, rate-limit, JSON,
or schema failure. Provider-reported usage totaled 53,433 input tokens and 5,267
output tokens. These are synthetic development measurements, not production
quality claims.

## Results

| Prompt | Coverage | Four-class exact | Overclaim | Partial to gap | Citation | Unsupported positive | Gate result |
|---|---:|---:|---:|---:|---:|---:|---|
| v3 | 10/12 | 9/12 | 1/12 | 1/4 | 5/5 | 0/5 | fail |
| v4 | 11/12 | 9/12 | 0/12 | 1/4 | 5/5 | 0/5 | safety pass, quality fail |
| v5 | 10/12 | 10/12 | 0/12 | 2/4 | 4/4 | 0/4 | safety pass, quality fail |

Prompt v4 is the selected development candidate. It eliminated the prompt-v2
`partial -> matched` overclaim and kept every emitted citation grounded. It still
missed one useful partial result (`matcher-dev-006`), so acceptable-evidence
accuracy was `5/6`. The frozen overall gate therefore did not pass.

Prompt v5 used a more explicit classification order but increased partial-to-gap
underclaim from one to two cases. Further prompt tuning stopped to avoid repeatedly
fitting the 12-case development set.

## Evidence Hashes

- prompt-v3 raw: `431153dc5044021c9043db489c0c9c7044d535b2dcca70e966d5b5fd62b5440f`
- prompt-v3 coverage: `eea0df2a724dcf140cd54e95f1a9a7af97585ead91cf930c41d03208bf60f1ae`
- prompt-v4 raw: `e944c4a08e99b51823ab03da183ad63012d26cba48a5c4d701a28303d0cf7063`
- selected prompt-v4 coverage/gates: `706062e5972e202a7d6060c9893caa5cfef203654b298b6265504392824d561f`
- prompt-v5 raw: `37b1e591ed52a74a4002b83a6fed1bfbe04b12aa9e7459adf3a729cc34fd0943`
- prompt-v5 coverage: `0def44fed3555da977360eedaa24308f9c21aea4ac88943be653d4f20027ac55`

## Stop Decision

Do not run matcher holdout or enable the real matcher in the production worker.
The next author decision is whether a conservative one-partial underclaim is an
acceptable development limitation or whether the dataset/contract needs broader
examples before another model or prompt experiment. The old holdout labels also
require author review under rubric v2 before any one-time holdout execution.
