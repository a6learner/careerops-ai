# Groq Evidence Matcher Development Offline Rescore V2

## Scope

This report replays the saved raw output from the completed Groq development
recovery against evaluation rubric v2. It made `0` provider requests, did not
load or run matcher holdout, and did not change retrieval or the model. Prompt v2
was implemented separately but was not invoked by this replay.

Source report SHA-256:
`1fa9856801f8f64b96e09416b135cc6d6fabd12314ddcd0d5076a2b817101675`.
Development labels SHA-256:
`c8c3d535ae103ea21b4c24397e1021dc4fd7688b37f907563363a19d87329605`.

## Results

| Metric | Result |
|---|---:|
| Completed cases | 12 / 12 |
| Provider requests during replay | 0 |
| End-to-end verdict accuracy | 6 / 12 (`0.5000`) |
| Matcher-only verdict accuracy | 7 / 12 (`0.5833`) |
| End-to-end macro-F1 | `0.4583` |
| Matcher-only macro-F1 | `0.5393` |
| Matcher-only Experience ID accuracy | `1.0000` |
| Matcher-only source accuracy | `1.0000` |
| Matcher-only acceptable evidence accuracy | `1.0000` |
| Matcher-only canonical quote exact agreement | `0.0000` |
| Matcher-only atomic verdict accuracy | 5 / 9 (`0.5556`) |
| Matcher-only composite verdict accuracy | 2 / 3 (`0.6667`) |
| Matcher-only matched recall | `1.0000` |
| Matcher-only partial recall | `0.7500` |
| Matcher-only missing recall | `0.0000` |
| Matcher-only insufficient-evidence recall | `0.6667` |
| Citation grounding validity | `1.0000` |
| Unsupported-positive rate | `0.0000` |
| Replayed input/output tokens | 13,087 / 1,823 |

Token totals are copied from the saved source report; replay consumed no tokens.

## Error Attribution

- Generic matcher verdict errors: 5. The common evaluator records every
  candidate-conditioned mismatch without ambiguity exemptions.
- V1 model errors not explained by the legacy ambiguity: 2
  (`matcher-dev-004`, `010`). These disagree with both the available evidence and
  the clarified candidate-conditioned rubric.
- Retrieval miss: 1 (`matcher-dev-009`). The full library supports `matched`,
  but the Top-5 supports only `partial`; the model's `partial` is correct for the
  matcher-only target.
- V1-only legacy verdict-label ambiguity: 3 (`matcher-dev-003`, `007`, `011`). The v1
  wording allowed broad topical relevance to blur `missing` and
  `insufficient_evidence`. V2 still scores these verdicts wrong; the attribution
  explains the likely source and does not grant alternate-label credit.
- Canonical quote over-strictness: 6 positive cases. Every positive quote is
  grounded and contains an allowed evidence fragment, but none exactly equals the
  shorter canonical quote.

The prior matcher-only accuracy was `6/11` (`0.5455`) because it excluded the
retrieval-miss case. V2 evaluates all 12 cases against their
candidate-conditioned verdict, producing `7/12` (`0.5833`). End-to-end verdict
accuracy remains `0.5000`.

## Interpretation

The provider was reliable during the completed recovery, and positive-claim
safety passed on this synthetic set. Verdict selection remains below the proposed
development gates. The legacy prompt was ambiguous on three `missing` cases,
while two errors remain after that effect is separated. These results do not
establish production accuracy and do not authorize matcher holdout.

The machine-readable evidence is
`docs/metrics/2026-10-04-groq-evidence-matcher-development-offline-rescore-v2.json`.
