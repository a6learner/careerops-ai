# Gemini Embedding 2 One-Time Holdout Comparison - 2026-10-03

## Scope

This record evaluates the frozen lexical, vector, and weighted-RRF hybrid retrieval
configurations on the reviewed retrieval v2 holdout split. It is holdout evidence,
not production-retrieval evidence.

- Source state: `0a89ef87cf4ddd2661a021e81fc2fc3a1d41dad8` plus the reviewed
  holdout-readiness working-tree fixes.
- Provider/model: Google Gemini API, `gemini-embedding-2`.
- Output dimensionality: 1536.
- Holdout queries: 20 total; 15 positive and 5 with no relevant Experience.
- Reused document vectors: 40 from the frozen development cache.
- Live provider work: one query batch, one request attempt, 20 query inputs, and
  zero document inputs.
- Provider-reported input tokens: 384.
- Frozen vector threshold: `0.65`.
- Frozen hybrid configuration: threshold `0.65`, lexical weight `0.50`, vector
  weight `0.50`, and reciprocal-rank-fusion constant `k=60`.

## Observed Holdout Metrics

| Metric | Lexical | Vector | Hybrid |
|---|---:|---:|---:|
| Recall@1 | 0.6222 | 0.8222 | 0.8222 |
| Recall@3 | 0.7667 | 0.9667 | 0.9667 |
| Recall@5 | 0.7667 | 0.9667 | 0.9667 |
| Precision@5 | 0.2267 | 0.2667 | 0.2667 |
| Hit@1 | 0.8000 | 1.0000 | 1.0000 |
| Hit@3 | 0.8000 | 1.0000 | 1.0000 |
| Hit@5 | 0.8000 | 1.0000 | 1.0000 |
| MRR@5 | 0.8000 | 1.0000 | 1.0000 |
| Negative accuracy@5 | 0.4000 | 0.8000 | 0.4000 |
| Mean returned candidates | 2.0000 | 1.5000 | 2.3000 |

The JSON evidence preserves full-precision values and per-query rankings. Rounded
values are shown here only for readability.

## Pre-Registered Result

Vector and hybrid both passed the frozen success rule: Recall@5, negative
accuracy@5, Hit@5, and MRR@5 were each no worse than lexical, with at least one
strict improvement. Hybrid matched lexical negative accuracy rather than improving
it; vector improved negative accuracy as well as the positive-query metrics.

No threshold, fusion weight, model, input template, or success criterion was changed
after observing holdout results. This holdout is not available for retuning or a
second comparison.

## Reproducibility Evidence

- Frozen development comparison SHA-256:
  `19aa221b03b6795571407b680c5cadcaa5b1be80a6307253801f4dcee33f40b1`
- Frozen development vector cache SHA-256:
  `8b07d9f80dc40d0fa744bab038034f39e4f6a4f9a69f2fe5b44f6419d82ad7b8`
- Holdout query cache SHA-256:
  `ef7f1154240c7970d0785a50e0bf55e298216f3c6358511cd1743d47e05302c6`
- Holdout comparison JSON SHA-256:
  `49624bbbac86561fdb7e07d0feb17cd2c334d5e5871a350c00488c6ed3817b07`

All 20 cached vectors were revalidated as query-role, exactly 1536 finite values,
and non-zero norm. The report's query-cache hash matches the saved gzip artifact.

## Limitations

- The dataset is synthetic, small, and reviewed by one project author.
- Full and partial support both count as binary-relevant.
- The provider model uses a stable alias rather than an immutable version.
- Provider reliability, monetary cost, throughput, and latency distributions were
  not measured.
- A successful holdout does not authorize changing production Analysis Run
  retrieval behavior.
