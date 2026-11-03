# ADR-049: Batched Evidence Matching

## Status

Accepted by the author on 2026-11-01 (stage 2 of the matcher-reliability plan;
whole-run failure chosen over partial results). Implemented and verified locally
with fake providers. Measured against a real provider on the development set on
2026-11-02 (see Verification). The output-cap question at the end is open.

## Context

In large_scale_v1 the matcher sent every requirement of a job in one call with
an 800-token output cap (`GROQ_EVIDENCE_MATCHER_MAX_OUTPUT_TOKENS`). Analyses
succeeded as follows:

| Requirements | Succeeded |
|---|---|
| 1–5 | 29/31 |
| 6–10 | 23/40 |
| 11–15 | 7/35 |
| 16 or more | 0/44 |

The median parsed job has 11 requirements.

On the 59 successful runs, a least-squares fit of output tokens against
requirement count gives about 54 tokens per requirement plus about 136 fixed.
That fit comes from `results_real_run.json` in
`docs/metrics/2026-11-01-large-scale-eval-v1/`. It reaches the cap at roughly
12 requirements.

## Decision

- **Batching.** The worker splits a run's requirement candidate sets, in order,
  into batches of at most `MATCHER_BATCH_SIZE = 6`. Each batch is one matcher
  call.
  - By the fit above, a full batch needs about 6 × 54 + 136 ≈ 460 output tokens,
    well under 800. The headroom covers positive matches, which cost more
    tokens than gaps.
- **Per-batch input.** Each batch's input is built with the existing
  `build_evidence_matcher_input`, so it carries only that batch's requirements
  and their candidate experiences.
- **Per-batch validation.** Each batch's output goes through the same
  schema, programmatic and model-identity checks as before. Coverage is checked
  per batch.
- **Sequential calls.** Batches run one after another, so the adapter's request
  pacing and the provider's rate limits apply per call.
- **Whole-run failure.** The first failing batch fails the run with that batch's
  error code, and nothing is stored. Matches are persisted only after every
  batch validates, in the existing single completion transaction, so the
  database invariants are unchanged.
- **Tokens.** Stored token counts are the sum of the counts each call reported,
  including the failing batch when the provider returned them.
- **Logs.** The success log includes `batch_count`. An output rejection logs
  `batch_index` and `batch_count`.
- **Versioning.** The pipeline version gets a `matcher-batch-6` segment before
  the model name, for example
  `match-v2:…:evidence-matcher-schema-v1:evidence-matcher-prompt-v4:matcher-batch-6:openai/gpt-oss-20b`.
  - The `match-v2` retrieval prefix is unchanged, so embedding-space resolution
    still works.
  - A run created before this change has no segment and keeps the single-call
    behavior when it is recovered.
  - The analysis fingerprint includes the pipeline version, so new runs are not
    deduplicated against old ones.
- The prompt, schema, model and output cap are unchanged.

## Alternatives considered

- **Raise the output cap.** A 46-requirement job would need about 2,600 tokens
  in one call. One bad answer would still sink the whole run, and the cost of a
  failure grows with the job.
- **One call per requirement.** This is the most robust option, but a median job
  needs 11 calls instead of 2, which costs more fixed prompt tokens and more
  rate-limit budget.
- **Partial results.** When one batch fails, store the other batches and mark
  the rest "not analysed". Deferred: it needs a new state in the API and the
  database, and showing a failed batch as a gap would be a false claim.
- **Parallel batches.** Lower latency, but it bursts the provider's
  tokens-per-minute limit, which was the free tier's main failure in
  large_scale_v1.

## Consequences

- A median job now makes 2 sequential calls, and a 26-requirement job makes 5.
  Latency grows with job size.
- Input tokens per run grow, because the instructions are sent once per batch.
- Each batch sees only its own requirements. A model that used cross-requirement
  context before no longer can. Given the prompt's per-requirement rubric, this
  is not expected to matter, but it is not measured.
- Runs from before and after this change are not comparable without noting the
  pipeline version.

## Verification or evidence

- `tests/test_analysis_run_batching.py`:
  - Pipeline segment parsing: present, legacy and malformed.
  - Split boundaries for 0, 1, 6, 7 and 26 requirements.
  - 13 requirements give 3 calls, all matches in order, and summed tokens.
  - Each batch carries only its own candidate experiences.
  - A failing second batch fails the run, stores nothing and records the tokens
    spent.
  - A legacy pipeline run still makes one call.
- `tests/integration/test_analysis_batching_postgres.py`: submitting through the
  API and executing against PostgreSQL stores all 13 matches from batches of 6,
  6 and 1 in one completion.
- Gates on 2026-11-02:
  - `ruff check .` and `mypy --strict src` clean.
  - `lint-imports` 2 contracts kept.
  - Unit tests: 471 passed.
  - Integration (isolated compose stack): 26 passed, 1 skipped (needs a running
    worker), 2 deselected.
    - The live Groq test was deselected by design.
    - `test_dashboard_summary_cache_invalidation_and_archived_scope` was
      deselected because async Redis connections time out inside this sandbox.
      It fails the same way on the unchanged code.
- Real-provider development check
  (`docs/metrics/2026-11-02-matcher-batching-dev.md`): same 150 pairs, the
  original parse runs replayed, OpenRouter with Allowed Providers = Groq (sampled
  probes 3/3 before and after; provider of each request not recorded).
  - Success: 107/150, against 59/150 with one call. At 16 or more
    requirements: 21/44, against 0/44.
  - Remaining failures are mostly `finish_reason=length` in individual
    batches.
  - Over-claiming on the 48 pairs that succeeded in every arm: 4 and 7 for
    two single-call runs, 10 and 8 for two batch-6 runs. That is within
    run-to-run variation.
  - Every stored positive kept a validated quote.

## Open decision (author)

The remaining large-job failures can be rescued by a 1,600-token cap (39 of 43
failed pairs) or by batches of 3 (36 of 43). A plain re-run rescues 14 of 43.
On the rescued large jobs, about 8% of labeled requirements are over-claimed:
52/631 with cap 1,600 and 48/572 with batch 3. The product default therefore
stays at batch 6 with the 800 cap: a failed run is safer than an over-claimed
one. Changing this, or reducing over-claiming on large jobs first, is the
author's call. Over-claiming could be reduced by filtering heading-like
requirements in the parser or by tightening matcher validation.

Follow-up: ADR-050 adds the parser heading filter. With it, over-claiming in
the full run was 24/1,022, against 39/1,098 without it (separate runs, different
successful sets). On 50 pairs scored on the
same requirements, over-claims were 5 (original single call), 8 (batch 6) and
3 (batch 6 with the filter); see `docs/metrics/2026-11-03-heading-filter-dev.md`.
The cap question was resolved by ADR-051 (cap 2,000, author decision
2026-11-03); reducing over-claiming on hard jobs is the next stage.
