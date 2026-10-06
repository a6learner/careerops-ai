# Fake Evidence Matcher Development Pipeline Record - 2026-10-04

## Scope

This record exercises the author-approved matcher v1 development dataset through
the deterministic fake matcher and evaluation harness. It is pipeline evidence,
not semantic matcher-quality evidence and not a baseline for selecting a real
provider or prompt.

- Git state: `6041cf378004dc65c2634c666194a61465a565ab` plus the P1-5 working tree
- Dataset: 12 synthetic development cases; 3 per verdict
- Matcher-eligible cases: 11
- Intentional retrieval misses: 1
- Provider: `fake`
- Real provider requests: 0
- Holdout cases evaluated: 0
- Corpus SHA-256: `139729a73aa99dc6cd6a9199d8c1b44e901e3d4cb1171ef4abd4990071fd1d0f`
- Development-case SHA-256: `3c43b7d472270bcedaba3397abeea18a05ec3b781c32a4ed2521f9c396d58efa`

The immutable machine-readable result, including every raw and validated case
result, is stored in `2026-10-04-fake-evidence-matcher-development.json`.

## Observed Pipeline Output

| Metric | Result |
|---|---:|
| Completed cases | 12 / 12 |
| Schema pass rate | 1.0000 |
| Provider failures | 0 |
| Output failures | 0 |
| End-to-end verdict accuracy | 0.2500 |
| Matcher-only verdict accuracy | 0.2727 |
| End-to-end macro-F1 | 0.1071 |
| Matcher-only macro-F1 | 0.1154 |
| Citation validity | 1.0000 |
| Unsupported positive claim rate | 0.0000 |
| Confidence cases | 0 |

## Interpretation

The run proves that approved hashes, typed matcher input/output, case-level
validation, separated matcher-only/end-to-end aggregation, and immutable report
writing work together offline. All twelve fake invocations completed without a
provider or schema failure, and every emitted citation passed grounding checks.

The low verdict and exact-match scores are expected because
`FakeEvidenceMatcher` is deterministic CI infrastructure rather than a semantic
judge. It selects a fixed safe behavior and is not tuned to these labels. These
scores must not be presented as real matcher accuracy or used to compare provider
quality. Zero unsupported positive claims demonstrates the exercised validation
path, not a measured production failure rate.

## Command

```powershell
.\.venv\Scripts\python -m careerops.evaluation.run_evidence_matcher `
  --experiences evals/evidence_retrieval_v2/experiences.json `
  --cases evals/evidence_matcher_v1/development_cases.json `
  --review-manifest evals/evidence_matcher_v1/review_manifest.json `
  --output docs/metrics/2026-10-04-fake-evidence-matcher-development.json `
  --git-revision 6041cf378004dc65c2634c666194a61465a565ab+p1-5b-working-tree
```

## Verification

```text
Focused P1-5a/P1-5b tests: 52 passed
Strict mypy: no issues in 108 source files
Ruff: all checks passed
Import contracts: 2 kept, 0 broken
pip check: no broken requirements
git diff --check: passed
```

The evaluator verified the approved corpus and development-case hashes before
writing the report. Focused tests also prove that an existing output cannot be
overwritten and that the development runner rejects the holdout split.

## Limitations

- All inputs are synthetic and were reviewed by one project author.
- The fake matcher provides no evidence about real-provider semantic quality.
- Latency excludes API, queue, database, worker, and network time.
- Fake token counts and confidence are absent by design.
- Candidate lists are frozen matcher inputs, not a new retrieval benchmark.
- The matcher holdout remains sealed and unobserved.
- Approval and this fake run do not authorize a real-provider request.
