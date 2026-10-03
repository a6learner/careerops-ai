# 0022 Real Embedding Evaluation

## What Changed

The repository now has a development-only evaluation path for comparing lexical,
real vector, and weighted-RRF hybrid retrieval. It includes a default-off Gemini
adapter, versioned asymmetric inputs, an immutable comparison report, resumable
vector cache, deterministic cosine ranking, development-only parameter selection,
and explicit provider failure classes.

Production Analysis Runs and embedding workers remain unchanged. No real provider
request is made by default tests or automated verification. One separately
authorized development run was completed on 2026-10-01 with 80 synthetic inputs,
two single-attempt requests, and zero holdout inputs. Its evidence is recorded in
`docs/metrics/2026-10-01-gemini-embedding-2-development.md`.

## Why It Exists

The existing fake embedding proves lifecycle behavior but cannot measure semantic
retrieval. This stage separates provider compatibility and retrieval quality from
the production path, so an experiment cannot silently change user-visible evidence
matching.

## Failure Modes It Prevents

- A default command or CI job consuming provider quota.
- Real resumes, JDs, or personal Experiences reaching a free-tier provider.
- Query and document text using incompatible retrieval instructions.
- Wrong-dimension, non-finite, zero, missing, or reordered vectors entering ranking.
- Floating ties changing order between runs.
- A partial provider failure overwriting the lexical baseline or producing a
  complete-looking comparison.
- Re-embedding a validated corpus after only the query batch fails.
- Hybrid parameters being tuned against holdout failures.
- A provider alias change making an old result impossible to reconstruct.

## How To Verify It

Run the offline focused tests:

```powershell
.\.venv\Scripts\python -m pytest `
  tests/test_gemini_embedding_evaluation_provider.py `
  tests/test_embedding_retrieval_evaluation_v2.py -ra
```

Run all normal quality gates without setting a live-provider flag:

```powershell
.\.venv\Scripts\python -m pytest -ra
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
.\.venv\Scripts\python -m pip check
```

The separately authorized real command is documented in README. It must use new
cache and output filenames and must report `holdout_input_count=0`.

The 2026-10-01 evidence passed those checks: all 80 vectors were exactly 1536
finite, non-zero values; the provider reported 3,104 input tokens; and both the
selected vector and hybrid configurations passed the pre-registered development
gate. Holdout remains sealed.

## What You Must Understand

Level 1:

- Provider success, output integrity, and retrieval-quality success are separate
  claims.
- Query/document instructions are part of the embedding model contract and must be
  versioned like a prompt.
- A saved vector cache is required for reproducibility when a provider alias can
  change over time.
- Rank fusion avoids pretending lexical integers and cosine values share one scale.
- Threshold and weight selection belong only on development; holdout is a one-time
  test of the frozen choice.
- Free quota does not remove data-governance obligations.

Level 2:

- The adapter uses synchronous batch embedding through `httpx`, with one attempt in
  the first authorized run.
- Cache keys bind role, input version, and exact rendered text.
- Cosine values are rounded to 12 decimals and UUIDs break remaining ties.
- An incomplete cache can contain one validated batch, but only a complete cache can
  produce metrics.
- The evaluator recomputes lexical rankings and rejects any difference from the
  saved v2 baseline.

## Knowledge Check

1. Why must the same raw text have different cache identities when used as a query
   and as a document?
2. Why is a 1536-value response still invalid if every value is zero?
3. Why is weighted RRF safer than adding lexical scores directly to cosine values?
4. What may be reused after the document batch succeeds and the query batch fails?
5. What exact conditions keep a Gemini call out of default tests and CI?
6. Why can a successful development comparison still not justify a production
   retrieval switch?
7. What must happen if a holdout failure suggests a new threshold or weight?
