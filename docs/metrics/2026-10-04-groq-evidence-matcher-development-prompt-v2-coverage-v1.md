# Groq Evidence Matcher Prompt V2 Coverage V1 Offline Rescore

## Scope

This immutable report derives three-class coverage from the saved prompt-v2
development report. It made zero provider calls, did not read or run matcher
holdout, and did not modify frozen labels, retrieval, or historical metrics.

Source report SHA-256:
`129024cd278d1d5ac0fcef5e133db0717f34ea67df98ff7c1b601c00c7c1d24e`.
Coverage report SHA-256:
`138b92d3b97de95dc40bcc43f1c7bb4f6480aaa08264894a52c004fd29a6dd5a`.

## Failure And Denominator Policy

- Primary coverage and four-class accuracy use all 12 cases.
- Provider/output failures count as incorrect; no gap is inferred.
- The 11-case schema-valid metric is diagnostic only.
- Gap-subtype differences count as coverage-correct but four-class incorrect.

## Results

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---:|
| Matcher-only coverage | 9 | 12 | `0.7500` |
| End-to-end coverage | 9 | 12 | `0.7500` |
| Schema-valid matcher coverage, diagnostic | 9 | 11 | `0.8182` |
| Four-class exact verdict | 8 | 12 | `0.6667` |
| Gap-subtype difference | 1 | 12 | `0.0833` |
| Any coverage overclaim | 1 | 12 | `0.0833` |
| Any coverage underclaim | 1 | 12 | `0.0833` |
| Gap to positive | 0 | 6 expected gaps | `0.0000` |
| Partial to matched | 1 | 4 expected partials | `0.2500` |
| Partial to gap | 1 | 4 expected partials | `0.2500` |
| Citation validity | 5 | 5 emitted positives | `1.0000` |
| Unsupported positive | 0 | 5 emitted positives | `0.0000` |

## Case Attribution

- `matcher-dev-004`: expected `insufficient_evidence`, predicted `missing`;
  coverage is still `gap`, so primary coverage is correct.
- `matcher-dev-008`: `invalid_schema`; counted incorrect, with no inferred
  semantic verdict. The historical report lacks raw response and structural
  diagnostic data, so the exact failed field is unknown.
- `matcher-dev-009`: expected `partial`, predicted gap; one proven resume-
  strengthening condition was missed.
- `matcher-dev-010`: expected `partial`, predicted `matched`; grounded sync
  evidence was overextended to unproven encrypted storage.

## Interpretation

Three-class coverage better reflects the product goal than four-class exact
accuracy alone, but the run is not ready for holdout. The schema failure and
`partial -> matched` overclaim violate proposed safety gates, while
`partial -> gap` misses useful evidence. A further real development run is not
worth doing until an offline prompt revision directly addresses these directions
and the proposed gates are reviewed and frozen.

The machine-readable report is
`docs/metrics/2026-10-04-groq-evidence-matcher-development-prompt-v2-coverage-v1.json`.
