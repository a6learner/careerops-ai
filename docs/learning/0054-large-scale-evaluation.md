# 0054 Large-Scale Development Evaluation (large_scale_v1)

## What Changed

- A development dataset in `evals/large_scale_v1/`: 302 real public job descriptions, 50 fictional resumes
  (214 experiences) and 150 resume × JD pairs.
- Model-made labels: parser labels for all 302 JDs and matcher labels for 148 pairs, each from two independent
  labelers plus adjudication, committed before the scored runs.
- A harness in `scripts/large_eval/`: a resumable driver that goes through the real API and worker, an exporter,
  a scorer with Wilson intervals, a retrieval check and a fake-provider scale test.
- Results in `docs/metrics/2026-11-01-large-scale-eval-v1.md` (ADR-047). No product code changed.

## Why It Exists

The earlier real-data walkthrough used 3 job descriptions and 1 CV. It found real problems, but 3 samples can't
say how often they happen. Interview claims need rates with sample sizes, not anecdotes.

## What It Found

- The matcher's one-call design breaks on larger jobs: 29/31 analyses succeeded at 1–5 requirements, 7/34 at
  11–15 and 0/43 at 16 or more. The median parsed job has 10 requirements.
- Where the matcher succeeded it was conservative: over-claim 1.8%, under-claim 13.1%, and it found none of the
  33 labeled partial matches. No stored positive claim lacked a validated quote.
- The parser keeps grounding but misses requirements: precision 84.0%, recall 57.7%, and only 44.0% recall on
  responsibility lines. Two parses of the same JD on the same host gave the same requirement set only 8 of 19 times.
- `MATCHER_PROVIDER_FAILED` mostly meant "Groq's schema check rejected the model output", not an outage.
- DOCX CV import produced one draft per CV; Markdown split all 214 experiences correctly.
- With fake providers, 7,500 analyses drained at about 5 per second and idle reads stayed under 18 ms p95.

## Failure Modes The Method Prevents

- **Tuning on the test.** Labels were committed before the matcher ran on those pairs, and no prompt or parameter
  changed during the run.
- **Mixing providers in one number.** OpenRouter first routed identical requests to four upstreams. Analyses
  waited until the provider was pinned, and the scorer drops runs outside that period and reports parser results
  per period.
- **One labeler's bias becoming "truth".** Two labeler families, Cohen's κ, a rejected low-effort label set kept
  for transparency, and blinded adjudication. The adjudicator still favored the Claude labeler (93 of 122), which
  the record states.
- **Retries hiding failures.** The driver records the first attempt and every retry, and caps retries per key so
  a deterministic HTTP 400 or 413 is not mistaken for a quota problem.
- **Driver timeouts read as product failures.** The scale numbers come from the database, not the client poller,
  which gave up on 6,132 runs that later succeeded.

## How It Was Verified

- The harness passes `ruff` and `mypy --strict` (`scripts/large_eval`), and product code under `src/` is unchanged.
- Label files are validated (every quote is an exact substring of the cited field) and committed with their
  agreement and adjudication statistics.
- `score.py` reproduces every number in the record from the saved artifacts.
- A SQL check on the evaluation database before it was deleted found 0 positive matches without a valid quote.

## What The Author Must Understand

- Level 1: why a development set built and scored together can't be a holdout, and what a fresh holdout needs.
- Level 1: Wilson intervals: why 0/24 is reported as 0–13.8% and not as "never".
- Level 1: the difference between an availability failure and a contract failure, and why the error code matters.
- Level 1: why the matcher fails more as the requirement count grows (one call, fixed 800-token output cap), and
  the design options: batching requirements, a larger cap, or per-requirement calls.
- Level 2: how the driver's checkpoint, idempotency keys and retry cap make a multi-day run resumable.

## Knowledge Check

1. Why were the M2 matcher labels committed before any M2 analysis ran, and what would go wrong otherwise?
2. The matcher succeeded on 59 of 148 pairs. Why can't its 1.8% over-claim rate be read as the rate for all jobs?
3. A request returns HTTP 200 but the run fails with `MATCHER_PROVIDER_FAILED`. Walk through how that happened.
4. Why did the analyses wait for the OpenRouter provider pin, while the parses already run were kept?
5. Repeat parses on the same host gave identical requirement sets 8 of 19 times. What does that mean for caching
   parse results and for comparing two analyses of "the same" job?
6. Hybrid recall@5 was 74.9% (M1) and lexical 60.8%. Why is this not automatic with 4–8 experiences per resume?
7. The scale driver reported 6,132 timeouts, yet the record says 7,500/7,500 analyses succeeded. Which source is
   right and why?
