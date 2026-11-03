# ADR-051: Evidence Matcher Output Cap of 2,000 Tokens

## Status

Accepted by the author on 2026-11-03 (cap value and "raise now, fix over-claiming
next" chosen by the author). Implemented and verified locally with fake providers.
The real-provider development check is recorded separately (see Verification).

## Context

After ADR-049 (batches of 6) and ADR-050 (heading filter), most remaining analysis
failures were single batches truncated at the 800-token output cap: 40 of the 44
failures in `docs/metrics/2026-11-03-heading-filter-dev/worker_log_counts.json`.
`gpt-oss-20b` counts its reasoning tokens against the cap, so a batch that normally
needs about 440 tokens sometimes runs past 800.

The 800 cap was set as a budget for Groq's free-tier 8,000 tokens per minute
(ADR-026 and ADR-029), not as a correctness limit.

Evidence on the 43 pairs that failed in the batch-6 run
(`docs/metrics/2026-11-02-matcher-batching-dev/`):

| Option | Rescued |
|---|---|
| Plain re-run at 800 | 14/43 |
| Batches of 3 at 800 | 36/43, about 2x input tokens, p95 latency 43 s |
| Cap 1,600 | 39/43, no truncation left; the other 4 were schema or ID errors |

A read-only analysis of those saved runs found that over-claiming on the rescued hard
jobs does not depend on output length:
- In the cap-1,600 run, batches within 800 tokens over-claimed 44/586 and longer
  ones 5/28.
- The batch-3 run, which never passed 800 tokens per batch, was at 46/555.
- Excluding headings changed it little (52 to 49).

These jobs over-claim at about 8% whichever way they are rescued. Over-claiming
there is a matcher-quality problem, separate from the cap.

## Decision

- **Cap.** New analysis runs use an output cap of `MATCHER_OUTPUT_CAP = 2000`:
  the tested 1,600 plus headroom.
- **Versioning.** The cap is recorded in the run's pipeline version as a
  `matcher-cap-2000` segment between the batch segment and the model name. The
  worker reads it through `matcher_output_cap_from_pipeline`.
  - Runs created earlier have no segment and keep the 800 cap.
  - An invalid or duplicated segment makes the matcher misconfigured, so the run
    fails without a provider call.
- **Unchanged:** the prompt, schema, model, batch size, validation, database and
  API.

## Alternatives considered

- **Retry a truncated batch with a larger cap.** The cap only stops generation,
  so any answer that fits in 800 tokens is identical under a 2,000 cap. Retrying
  gives the same results plus a wasted first call and extra latency.
- **Smaller batches.** They rescued fewer jobs, roughly doubled input tokens
  because the instructions repeat per call, and had higher latency.
- **A much larger cap (4,000).** Nothing above 1,600 was measured. A runaway call
  would cost and wait more for no measured gain.
- **Keep 800 until over-claiming is fixed.** The author chose to raise now and
  fix over-claiming as the next stage, rather than keep large jobs failing.

## Consequences

- **Cost.** The worst-case output per call goes from 800 to 2,000 tokens, but
  only calls that need it use it.
- **Free tier.** The cap is no longer sized for Groq's free-tier tokens-per-minute
  limit. On that tier, larger calls are more likely to be rate-limited.
- **Over-claiming becomes visible.** More hard, large jobs complete, and their
  over-claiming (about 8% of labeled requirements in development data) now
  reaches users instead of a failed run. Every positive still cites a validated
  quote; the over-claims are judgments the labels consider too strong.
  Reducing them is the next stage.
- **Comparability.** Pipeline versions now differ by cap, so runs before and
  after are distinguishable.

## Verification or evidence

- `tests/test_analysis_run_batching.py`: the cap segment's position and value,
  legacy pipelines without a cap, and invalid segments.
- `tests/test_evidence_matcher_factory.py`: a run with `matcher-cap-2000` builds
  a matcher with cap 2,000, a legacy run gets 800, and an invalid segment is
  misconfigured.
- Gates on 2026-11-03:
  - `ruff check .`, `mypy --strict src` and `lint-imports` clean.
  - Unit tests: 496 passed.
  - Integration on a clean database: 26 passed, 1 skipped, 2 deselected.
- Real-provider development check: `docs/metrics/2026-11-03-matcher-cap-dev.md`.
  - 138/148 analysable pairs succeeded, against 104 at the 800 cap.
  - No `finish_reason=length` failures remained.
  - Pairs only the 2,000 cap completed over-claimed 47/588 (8.0%).
  - On 100 pairs both completed, over-claims were 23 against 29 (paired p = 0.33).
  - All 190 stored positives kept a validated quote.
