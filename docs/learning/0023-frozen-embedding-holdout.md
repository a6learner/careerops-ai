# 0023 Frozen Embedding Holdout

## What Changed

P1-3b adds an independent, default-off holdout evaluator. It validates the exact
committed P1-3a development report and cache, reuses 40 document vectors, embeds at
most 20 holdout queries in one batch, and evaluates only the frozen vector and
hybrid configurations.

No real holdout request, ranking, or metric has been produced by this implementation
stage. Default tests use development-derived toy queries marked as holdout.

## Why It Exists

A holdout is useful only while its outcomes cannot influence model, prompt,
threshold, fusion weight, or success-criterion selection. A separate runner makes
the scientific boundary executable instead of relying on operator memory.

Reusing validated corpus vectors also reduces live inputs and prevents two corpus
representations from being mixed accidentally inside the same holdout run.

## Failure Modes It Prevents

- A development opt-in accidentally unlocking the holdout.
- Substituting a changed development report or vector cache.
- Re-running the threshold or alpha grid after holdout labels become visible.
- Re-embedding the corpus and spending 40 unnecessary inputs.
- Mixing query vectors with the wrong model, dimension, corpus, or input version.
- A failed provider request producing a complete-looking report.
- A reporting retry issuing a second provider request after query vectors are saved.
- Windows line endings making a committed JSON artifact appear different on Linux.

## How To Verify It

Run the focused offline tests:

```powershell
.\.venv\Scripts\python -m pytest tests/test_embedding_holdout_v2.py -ra
```

Confirm that the test file does not reference the real holdout path:

```powershell
rg -n "holdout_queries.json" tests/test_embedding_holdout_v2.py
```

The command should return no match. Then run the normal repository quality gates.
Do not set `CAREEROPS_RUN_EMBEDDING_HOLDOUT` during verification.

## What You Must Understand

Level 1:

- Development chooses parameters; holdout estimates how those frozen choices
  generalize. Using holdout to choose again destroys that separation.
- A success criterion must be fixed before observing the result, including what
  counts as a non-regression and what happens after failure.
- Provider-call success, vector integrity, holdout success, and production readiness
  are four different claims.
- An experiment that fails its holdout criterion is still a valid result.

Level 2:

- The runner binds the holdout to exact P1-3a artifact hashes and parameters.
- Only query embeddings are stored in the P1-3b cache; document embeddings remain in
  the frozen P1-3a cache.
- A complete cache can recover report generation without another provider call.
- The holdout flag is distinct and invocation-local, while the API key stays in the
  ignored `.env` file.

## Knowledge Check

1. Why is changing `alpha` after seeing holdout Recall@5 methodologically invalid?
2. Why does P1-3b reuse document vectors instead of embedding the corpus again?
3. What identities must match before the provider receives any holdout query?
4. What gets saved if the only query batch receives HTTP 429?
5. Why can a complete query cache be reused after a local report-write failure?
6. What must happen if vector passes the holdout rule but hybrid fails it?
7. Why does a successful holdout still not authorize a production retrieval switch?
