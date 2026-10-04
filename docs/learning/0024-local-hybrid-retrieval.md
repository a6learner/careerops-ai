# 0024 Local Exact Hybrid Retrieval

## What Changed

Analysis workers can now combine lexical candidates with exact pgvector cosine
ranking through fixed weighted RRF. Gemini and fake providers share one typed
embedding-space contract, while model and input-version filters prevent vector-space
mixing. Provider failure or unavailable vectors fall back to lexical retrieval.

Analysis recovery also gained attempt fencing so an old worker cannot complete a
run after recovery has created a newer attempt.

Provider authorization is process-only. Durable embedding work selects its provider
from the stored model/input version, and Analysis Runs store the complete retrieval
space in their pipeline version so later configuration changes cannot reinterpret
queued work.

## Why It Exists

The project now connects the previously isolated retrieval evidence to the real
worker workflow without changing the API or weakening evidence validation. Exact
search is simpler and fully auditable for a small Experience library.

## Failure Modes It Prevents

- Cross-user or deleted Experiences entering vector candidates.
- Fake, stale, wrong-model, or wrong-input-version vectors mixing with Gemini.
- Provider outages blocking otherwise valid lexical analysis.
- Recovery changing vector availability after the run was accepted.
- An old Analysis worker persisting after a newer recovery attempt.
- Approximate-index behavior obscuring deterministic tests at small scale.
- Persisted `.env` authorization silently enabling later paid requests.
- Configuration changes causing queued work to execute in a different vector space.

## How To Verify It

Run the normal offline quality gates, then run integration tests with local
PostgreSQL and Redis using `CAREEROPS_RUN_INTEGRATION=1`. A real Gemini compatibility
test requires separate authorization and `CAREEROPS_RUN_EMBEDDING_INTEGRATION=1`.

## What You Must Understand

Level 1: pgvector score calculation belongs in the repository, while fallback and
RRF are business workflow decisions in the service layer.

Level 1: partial hybrid retrieval keeps lexical coverage over the full library and
uses semantic ranking only for provenance-valid rows. It improves availability but
must expose partial coverage honestly.

Level 1: attempt fencing protects persisted results, not provider-call exactly-once
execution. A recovered task may recompute, but an old attempt cannot win the write.

Level 2: `embedded_at <= analysis_run.created_at` freezes which completed vectors a
run may observe without adding a snapshot table or migration.

## Knowledge Check

1. Why is exact pgvector search preferable to HNSW for about 40 Experiences?
2. Which provenance fields prevent fake and Gemini vectors from mixing?
3. Why does a query-provider failure produce lexical fallback instead of a failed run?
4. How does the creation-time cutoff make recovery deterministic?
5. What race is prevented by checking `analysis_runs.attempt` during completion?
