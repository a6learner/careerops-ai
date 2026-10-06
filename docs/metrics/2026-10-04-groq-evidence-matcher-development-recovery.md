# Groq Evidence Matcher Development Recovery - 2026-10-04

## Scope

This authorized recovery resumes the immutable partial development report and
calls only `matcher-dev-007` through `matcher-dev-012`. It uses the same frozen
model, prompt, schema, corpus, labels, and candidate lists. It does not recall the
first six successful cases, read or call matcher holdout, change retrieval, or
fall back to the fake matcher.

- Provider/model: Groq `openai/gpt-oss-20b`
- Prior report SHA-256: `a2df1930b1075c7068584845dd3ca2345be0917fed42e907fdae1b05b3173d96`
- New request budget / used: 6 / 6
- Minimum request-start interval: 11 seconds
- Cumulative real development attempts: 18
- Holdout attempts: 0
- Corpus SHA-256: `139729a73aa99dc6cd6a9199d8c1b44e901e3d4cb1171ef4abd4990071fd1d0f`
- Development-case SHA-256: `3c43b7d472270bcedaba3397abeea18a05ec3b781c32a4ed2521f9c396d58efa`

The immutable merged case-level report is stored in
`2026-10-04-groq-evidence-matcher-development-recovery.json`.

## Recovery Result

| Metric | Result |
|---|---:|
| Completed development cases | 12 / 12 |
| Provider failures | 0 |
| Output failures | 0 |
| Schema pass rate | 1.0000 |
| End-to-end verdict accuracy | 0.5000 |
| Matcher-only verdict accuracy | 0.5455 |
| End-to-end macro-F1 | 0.4583 |
| Matcher-only macro-F1 | 0.5250 |
| End-to-end exact match | 0.1667 |
| Matcher-only exact match | 0.1818 |
| Positive evidence exact accuracy | 0.0000 |
| Gap accuracy | 0.3333 |
| Citation validity | 1.0000 |
| Unsupported positive claim rate | 0.0000 |
| Confidence Brier score | 0.1473 |

Recovery itself reported 6,520 input and 742 output tokens. The merged successful
case total is 13,087 input and 1,823 output tokens. Provider billing was not
measured. At the provider's published 2026-10-04 list prices, the merged successful
token total is approximately $0.00153; this excludes unknown failed-request
accounting and is not a billed amount.

## Interpretation

Pacing resolved the short-window TPM failure: all six recovery requests completed,
and the merged report has no provider or output failure. This validates bounded
recovery and immutable result merging.

Semantic quality does not yet justify freezing for holdout. The matcher correctly
identified four of six positive verdict classes from the first half but confused
`missing` with `insufficient_evidence`; in recovery it also downgraded one
intentional retrieval miss from `matched` to `partial` and upgraded one `partial`
case to `matched`. Both positive and gap distinctions need development work.

All six emitted positive citations were grounded, and no unsupported positive
claim passed validation. However, none exactly matched the single frozen gold
Experience/source/quote tuple. Citation safety and exact-gold agreement therefore
remain distinct: the model cited valid evidence, but not the evaluator's canonical
quote selection.

## Latency Note

The merged mean of 4,999.75 ms includes deliberate pacing waits inside five
recovery case timers. It is evaluation elapsed time, not provider response latency
and not an API, queue, database, worker, or production latency benchmark.

## Verification

The runner hash-validated the approved dataset and prior report, selected exactly
the six failed case IDs, used six requests, recorded cumulative attempts as 18,
preserved the first six case results, wrote a new file, and returned zero failures.
Offline tests independently exercise the same recovery merge and pacing behavior.

## Holdout Decision

Matcher holdout remains sealed. Development verdict and exact-evidence metrics are
not yet strong enough to freeze the current prompt/model as the holdout candidate.
Any prompt or policy change must use development data only and produce a new
immutable development report before a separately authorized holdout run.
