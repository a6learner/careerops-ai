# Gemini Embedding 2 Development Retrieval Comparison - 2026-10-01

## Scope

This record compares the unchanged lexical retriever with exact vector cosine
ranking and weighted-RRF hybrid ranking on the reviewed retrieval v2 development
split. It is development evidence only, not holdout or production evidence.

- Git state: `c751940` plus the P1-3a working tree
- Provider/model: Google Gemini API, `gemini-embedding-2`
- Output dimensionality: 1536
- Corpus: 4 synthetic profiles with 40 Experiences
- Development queries: 40 total; 30 positive and 10 with no relevant Experience
- Holdout inputs and calls: 0
- Document input version: `gemini-embedding-2-search-document-v1`
- Query input version: `gemini-embedding-2-search-query-v1`
- Project billing tier at run time: free tier

The machine-readable comparison, including every development ranking, is stored in
`2026-10-01-gemini-embedding-2-development-comparison.json`. The validated vector
cache is stored in
`2026-10-01-gemini-embedding-2-development-vectors.json.gz`.

## Provider Run

| Batch | Unique inputs | Request attempts | Provider-reported tokens |
|---|---:|---:|---:|
| Documents | 40 | 1 | 2,360 |
| Development queries | 40 | 1 | 744 |
| Total | 80 | 2 | 3,104 |

The provider did not return billable-character usage. Cache creation and completion
timestamps span 2.826 seconds; this is run bookkeeping, not a latency benchmark.
Provider billing charge was not measured.

All 80 cached vectors were revalidated as exactly 1536 finite values with a
non-zero norm. The cache completed without retry, partial failure, or recovery.

## Selected Development Configurations

- Vector: cosine threshold `0.65`.
- Hybrid: cosine threshold `0.65`, lexical weight `alpha=0.50`, vector weight
  `1-alpha=0.50`, and reciprocal-rank-fusion constant `k=60`.
- Both configurations passed the pre-registered development gate.

The grid and selection order were fixed before the real run. No holdout result was
read or used to choose these values.

## Observed Development Metrics

| Metric | Lexical | Vector | Hybrid |
|---|---:|---:|---:|
| Recall@1 | 0.6611 | 0.8611 | 0.8611 |
| Recall@3 | 0.8333 | 0.9444 | 0.9833 |
| Recall@5 | 0.8333 | 0.9444 | 0.9833 |
| Precision@5 | 0.2133 | 0.2333 | 0.2533 |
| Hit@1 | 0.7667 | 1.0000 | 1.0000 |
| Hit@3 | 0.8667 | 1.0000 | 1.0000 |
| Hit@5 | 0.8667 | 1.0000 | 1.0000 |
| MRR@5 | 0.8167 | 1.0000 | 1.0000 |
| Negative accuracy@5 | 0.3000 | 0.7000 | 0.3000 |
| Mean returned candidates | 2.0000 | 1.4000 | 2.4250 |

The JSON evidence preserves full-precision values. Rounded values are shown here
only for readability.

## Interpretation

On this synthetic development split, vector retrieval improved every positive-query
metric and negative accuracy over lexical. The selected hybrid improved Recall@3,
Recall@5, Precision@5, Hit@1/3/5, and MRR@5 while matching lexical negative
accuracy@5. Hybrid therefore passed the pre-registered rule requiring no regression
in Recall@5, Hit@5, MRR@5, or negative accuracy@5 and at least one strict
improvement.

Hybrid returned more candidates than either lexical or vector, and its negative
accuracy did not improve over lexical. The vector-only configuration had lower
Recall@5 than hybrid but substantially better negative accuracy and fewer returned
candidates. These trade-offs remain development observations; they do not select a
production retriever.

## Reproducibility Evidence

- Corpus SHA-256:
  `139729a73aa99dc6cd6a9199d8c1b44e901e3d4cb1171ef4abd4990071fd1d0f`
- Development-query SHA-256:
  `ee78882ee3c627d4de1bc1e33e936b5ab4f3a4e615fc88b0002baf1c9c1a0d0e`
- Frozen lexical baseline SHA-256:
  `25d7703b355a184c8d0365557caa5483660893097060108c345993fc5814cbf8`
- Vector cache SHA-256:
  `8b07d9f80dc40d0fa744bab038034f39e4f6a4f9a69f2fe5b44f6419d82ad7b8`
- Comparison JSON SHA-256:
  `c3d9fe3bee8c78aaf50f5eb25eee568bd35e0af07323d2973a480c8a48236d24`

## Command

The key was read from the ignored repository-root `.env` file and was not placed in
the command, output, or evidence artifacts.

```powershell
$env:CAREEROPS_RUN_EMBEDDING_EVAL='1'
.\.venv\Scripts\python -m careerops.evaluation.run_embedding_retrieval_v2 `
  --experiences evals/evidence_retrieval_v2/experiences.json `
  --queries evals/evidence_retrieval_v2/development_queries.json `
  --review-manifest evals/evidence_retrieval_v2/review_manifest.json `
  --lexical-baseline docs/metrics/2026-09-21-lexical-retrieval-v2-development.json `
  --cache docs/metrics/2026-10-01-gemini-embedding-2-development-vectors.json.gz `
  --output docs/metrics/2026-10-01-gemini-embedding-2-development-comparison.json `
  --git-revision c751940-plus-working-tree-p1-3a `
  --provider gemini
Remove-Item Env:CAREEROPS_RUN_EMBEDDING_EVAL
```

## Limitations

- The data is synthetic, small, and used to select development parameters.
- One project author reviewed the labels; inter-annotator agreement is not measured.
- Full and partial support both count as binary-relevant.
- The stable provider model alias may change after this cached run.
- The free-tier provider may use submitted synthetic content to improve products.
- Holdout rankings and metrics remain unobserved.
- No production Analysis Run, database, API, worker, or retrieval behavior changed.
- Provider reliability, monetary cost, throughput, and latency distributions are
  not measured.
