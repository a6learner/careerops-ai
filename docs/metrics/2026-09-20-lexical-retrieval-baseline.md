# Lexical Evidence Retrieval Baseline - 2026-09-20

## Scope

This record measures the current deterministic lexical and exact-skill Top-5
retriever on the versioned synthetic development set. It is retrieval-quality
evidence only. It is not a production-accuracy, latency, throughput, reliability,
provider, token, or cost benchmark.

- Git state: `234a381` plus the P1-2a working tree
- Dataset: `evals/evidence_retrieval_v1.json`, version 1
- Corpus: 20 synthetic Experiences
- Queries: 27 total; 25 positive and 2 with no relevant Experience
- Retriever: `lexical-skill-v1`
- Candidate limit: 5
- Real embedding, evidence-matcher, or Groq requests: 0

The immutable machine-readable result, including every ranked candidate, is stored
in `2026-09-20-lexical-retrieval-baseline.json`.

## Metric Definitions

Recall@K is calculated per positive query as relevant IDs retrieved in the first K
positions divided by all labeled relevant IDs, then macro-averaged across positive
queries.

MRR@5 is the macro average reciprocal rank of the first relevant result for positive
queries. A positive query with no relevant result in the Top-5 receives zero.

For the two queries with no relevant Experience, success requires an empty Top-5
result. Their separate accuracy is not mixed into Recall or MRR.

## Observed Baseline

| Metric | Result |
|---|---:|
| Recall@1 | 0.8257 |
| Recall@3 | 0.8971 |
| Recall@5 | 0.9086 |
| MRR@5 | 0.9200 |
| No-relevant-returned accuracy@5 | 0.5000 |

The full-precision values remain in the JSON evidence file. Rounded values in this
table are for readability.

## Interpretation

Exact skill labels make many synthetic queries easy for the baseline, so the scores
must not be generalized beyond this development set. Recall@5 remains below one,
including deliberate paraphrase and multi-relevant cases. One of the two negative
queries returned lexical candidates, showing that positive token overlap alone is
not a reliable abstention rule.

These observations define comparison targets; they do not yet justify a vector or
hybrid production switch.

## Verification

Observed offline results after generating the report:

```text
Focused retrieval tests: 9 passed
Default pytest suite: 168 passed, 19 skipped
Strict mypy: no issues in 91 source files
Ruff: all checks passed
Import contracts: 2 kept, 0 broken
pip check: no broken requirements
git diff --check: passed
```

The skipped tests require PostgreSQL, Redis, a continuously running worker, or an
explicit live Groq request. Infrastructure integration was not rerun because this
stage changes no API, database, Redis, worker, or production retrieval behavior.

## Command

```powershell
.\.venv\Scripts\python -m careerops.evaluation.run_evidence_retrieval `
  --dataset evals/evidence_retrieval_v1.json `
  --output docs/metrics/2026-09-20-lexical-retrieval-baseline.json `
  --git-revision 234a381-plus-working-tree-p1-2a
```

## Limitations

- The set is small, synthetic, and used for development rather than held out.
- Relevance labels were authored once and have no inter-annotator agreement data.
- Binary relevance does not distinguish strong from weak evidence.
- The shared corpus is much smaller than a mature user's possible Experience set.
- Latency, throughput, provider behavior, token usage, and cost were not measured.
- No fake or real embedding vector contributed to this result.
