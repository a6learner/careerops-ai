# Lexical Evidence Retrieval V2 Development Baseline - 2026-09-21

## Scope

This record measures the unchanged deterministic lexical and exact-skill Top-5
retriever on the project-author-reviewed retrieval v2 development split. It is
retrieval-quality evidence only. It is not a holdout, production-accuracy,
latency, throughput, reliability, provider, token, or cost benchmark.

- Git state: `289bd0e` plus the P1-2b working tree
- Corpus: 4 synthetic profiles with 40 Experiences
- Development queries: 40 total; 30 positive and 10 with no relevant Experience
- Holdout queries evaluated: 0
- Retriever: `lexical-skill-v1`
- Candidate limit: 5
- Real embedding, evidence-matcher, or Groq requests: 0
- Corpus SHA-256: `139729a73aa99dc6cd6a9199d8c1b44e901e3d4cb1171ef4abd4990071fd1d0f`
- Development-query SHA-256: `ee78882ee3c627d4de1bc1e33e936b5ab4f3a4e615fc88b0002baf1c9c1a0d0e`

The immutable machine-readable result, including every ranked candidate, is stored
in `2026-09-21-lexical-retrieval-v2-development.json`.

## Metric Definitions

Recall@K is the macro average, over positive queries, of the fraction of all
labeled full-or-partial evidence returned in the first K positions.

Precision@5 is the macro average number of relevant candidates in the Top-5 divided
by five. The denominator remains five even when the retriever returns fewer results,
so abstaining cannot inflate precision.

Hit@K is the fraction of positive queries with at least one relevant candidate in
the first K positions. MRR@5 is the macro average reciprocal rank of the first
relevant result, using zero when none appears.

Negative accuracy@5 is calculated only on zero-relevance queries. A negative query
succeeds only when the retriever returns no candidate. Mean returned candidate count
is reported separately to expose abstention behavior.

## Observed Development Baseline

| Metric | Result |
|---|---:|
| Recall@1 | 0.6611 |
| Recall@3 | 0.8333 |
| Recall@5 | 0.8333 |
| Precision@5 | 0.2133 |
| Hit@1 | 0.7667 |
| Hit@3 | 0.8667 |
| Hit@5 | 0.8667 |
| MRR@5 | 0.8167 |
| Negative accuracy@5 | 0.3000 |
| Mean returned candidates | 2.0000 |

The JSON evidence preserves full-precision values. Rounded values are shown here
only for readability.

## Interpretation

The harder development set exposes limitations hidden by the smaller v1 dataset.
Six positive queries did not achieve complete Recall@5: four returned no relevant
candidate and two retrieved only half of their labeled evidence. The misses include
paraphrased, compound, and Chinese-to-English requirements.

Seven of ten negative queries returned at least one candidate. Shared domain or
technology vocabulary therefore remains a weak abstention signal. Precision@5 is
also low because the fixed candidate budget penalizes empty and irrelevant slots.

These results are not directly comparable to v1 as a regression measurement because
the corpus and labels changed. They establish the frozen development target against
which future vector and hybrid candidates can be compared. They do not justify a
production retrieval change.

## Verification

Observed offline verification after generating the report:

```text
Focused retrieval v2 tests: 7 passed
Default pytest suite: 175 passed, 19 skipped
Strict mypy: no issues in 94 source files
Ruff: all checks passed
Import contracts: 2 kept, 0 broken
pip check: no broken requirements
git diff --check: passed
```

The skipped tests require PostgreSQL, Redis, a continuously running worker, or an
explicit live Groq request. Infrastructure integration was not rerun because this
stage changes no API, database, Redis, worker, or production retrieval behavior.

The evaluator verified the approved manifest and both file hashes before writing
the report. The command refuses to overwrite an existing artifact and rejects the
holdout split.

## Command

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
D:\pdd\project\careerops-ai\.venv\Scripts\python.exe `
  -m careerops.evaluation.run_evidence_retrieval_v2 `
  --experiences evals/evidence_retrieval_v2/experiences.json `
  --queries evals/evidence_retrieval_v2/development_queries.json `
  --review-manifest evals/evidence_retrieval_v2/review_manifest.json `
  --output docs/metrics/2026-09-21-lexical-retrieval-v2-development.json `
  --git-revision 289bd0e-plus-working-tree-p1-2b
```

## Limitations

- The data is synthetic and covers four designed candidate profiles.
- One project author reviewed the labels; inter-annotator agreement was not measured.
- Full and partial support both count as binary-relevant for candidate retrieval.
- The development split may guide future retrieval design and is not a holdout.
- Holdout rankings and metrics remain unobserved.
- Latency, throughput, provider behavior, token usage, and cost were not measured.
- No fake or real embedding vector contributed to this result.
