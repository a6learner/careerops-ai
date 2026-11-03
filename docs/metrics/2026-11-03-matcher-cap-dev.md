# Matcher output cap 2,000 development check (2026-11-03)

This record measures ADR-051 (matcher output cap raised from 800 to 2,000 tokens) on top of ADR-049
(batches of 6) and ADR-050 (parser heading filter). It uses the same dataset, labels and method as
`2026-11-03-heading-filter-dev.md`. Every number comes from a file in
`docs/metrics/2026-11-03-matcher-cap-dev/` or from the earlier records it compares against.

**This is a development check, not a holdout.** The cap was chosen from failures on this dataset.

## Setup

| Item | Value |
|---|---|
| Code | commit in `code_commit.txt` (ADR-051); pipeline segments `matcher-batch-6:matcher-cap-2000` |
| Route | OpenRouter. The author's account setting Allowed Providers = Groq is not itself recorded in an artifact. Sampled probes before and after: 3/3 and 3/3 served by Groq (`route_probe_*.json`). The serving provider of each request was not recorded |
| Stack | fresh isolated compose project; environment in `stack_env.sh.txt` (the key is read from `.env` at runtime); one worker, 1 process × 4 threads; teardown output in `teardown.txt` |
| Embeddings | 214 of 214 embedding runs succeeded, and 0 analysis runs existed, when checked before the analyses (`embedding_status_before_analyses.txt`) |
| Parse runs | the same 150 large_scale_v1 parse runs, replayed with heading requirements removed (`replay_parses.py --drop-headings`); 148 analysable, 2 pairs had only headings |
| Comparison run | `batch6_noheadings` from `2026-11-03-heading-filter-dev.md`: identical except for the 800 cap, run earlier the same day on a different stack |

## Results

Source: `score_cap2000.json`. Comparison values are from `../2026-11-03-heading-filter-dev/score_noheadings.json`.

| Metric | Cap 800 (heading filter) | Cap 2,000 |
|---|---|---|
| Analyses succeeded (of 148) | 104 | 138 = 93.2% |
| Failure codes | 44 invalid schema | 9 invalid schema, 1 invalid contract |
| `finish_reason=length` in the worker log | 40 | 0 |
| Output tokens per successful run, p50 / p95 / max | 754 / 2,018 / 3,460 | 1,067 / 2,582 / 4,946 |
| Latency of successful runs, p50 / p95 | 8.7 s / 21.5 s | 10.7 s / 23.7 s |

Worker log for the cap-2,000 run (`worker_log_counts.json`):
- 7 `finish_reason=error` (provider-side schema rejection);
- 2 malformed IDs;
- 1 batch that returned 3 of its 6 requirements;
- 346 OpenRouter responses, all HTTP 200.

Success by requirement count (after heading removal), with the cap-800 run in brackets:

| Requirements | Cap 2,000 | Cap 800 |
|---|---|---|
| 1–5 | 30/31 | 31/31 |
| 6–10 | 37/39 | 32/39 |
| 11–15 | 34/36 | 19/36 |
| 16–20 | 22/24 | 13/24 |
| 21+ | 15/18 | 9/18 |

Against the labels, over all of its 138 successful analyses (1,547 labeled requirements):

| Metric | Value |
|---|---|
| Over-claim | 76/1,547 = 4.9% (3.9–6.1) |
| Labeled gap shown as positive | 50/1,206 = 4.1% (3.2–5.4) |
| Under-claim | 212/1,547 = 13.7% (12.1–15.5) |
| Coverage class exact | 1,259/1,547 = 81.4% (79.4–83.2) |

## Where the extra over-claiming comes from

The overall rate is higher than the cap-800 run's 2.3% because more hard jobs complete.
`paired_check.json` (`scripts/large_eval/paired_matcher_check.py`) splits it:

- **Pairs only the cap-2,000 run completed:** 47/588 requirements over-claimed = 8.0% (6.1–10.5). This
  matches the about 8% seen on the same hard jobs in the 2026-11-02 cap-1,600 and batch-3 runs.
- **Pairs both runs completed (100 pairs, 959 requirements):**
  - 831 had the same verdict.
  - 10 requirements were over-claimed only at cap 800 and 16 only at cap 2,000 (exact McNemar
    p = 0.33).
  - 26 had the exact coverage class only at cap 800 and 14 only at cap 2,000 (p = 0.08).
  - Totals (`arms_cap800_vs_cap2000_shared.json`): over-claim 23 against 29, coverage exact 831
    against 819, under-claim 105 against 111.
- **Same-configuration control:** two batch-6 runs from 2026-11-02 split 4/3 on both measures (281
  requirements, p = 1.0).

On pairs both runs completed, a 2,000 cap cannot change any batch whose answer fits in 800 tokens. It
can change a batch that, in this run, reasoned past 800 tokens and still finished. That is a possible
source of real difference, but a rough split by average output per batch places most of the difference
in short-output runs. The shared-pair differences are not statistically significant. The cap-2,000 run
is a little worse on them, but within what separate runs on different stacks can show.

Three-way comparison (`arms_original_cap800_cap2000_shared.json`; 51 pairs that succeeded in all three,
265 requirements):

| Metric | large_scale_v1 (one call) | Cap 800 | Cap 2,000 |
|---|---|---|---|
| Over-claim | 4 | 3 | 4 |
| Labeled gap shown as positive | 1/220 | 1/220 | 3/220 |
| Under-claim | 36 | 32 | 37 |
| Coverage exact | 225 | 230 | 224 |

## Evidence guarantee

Before the database was deleted, a SQL check found 190 positive matches, all from the cap-2,000 run.
None lacked an experience, a version, a non-blank quote or `quote_valid = true`
(`evidence_guarantee_check.txt`).

## Interpretation

- **Reliability.** Truncation is gone and 93% of analysable pairs complete, including 15 of 18 jobs
  with 21 or more requirements.
- **Cost.** About 8% of labeled requirements are over-claimed on the hard jobs that now complete.
  Every positive still cites a validated quote; the labels judge those quotes too weak. This is the
  trade-off the author accepted for ADR-051, with reducing it as the next stage.

## Not measured

- Money spent.
- Per-batch output tokens: only run totals are stored.
- Held-out quality: still needs a fresh holdout.

## Files

`docs/metrics/2026-11-03-matcher-cap-dev/`:
- Data and scores: `results_cap2000.json`, `driver_state_cap2000.jsonl`, `score_cap2000.json`.
- Comparisons: `paired_check.json`, `arms_cap800_vs_cap2000_shared.json`,
  `arms_original_cap800_cap2000_shared.json`.
- Logs and checks: `worker_log_counts.json`, `evidence_guarantee_check.txt`,
  `embedding_status_before_analyses.txt`, `teardown.txt`.
- Configuration and probes: `stack_env.sh.txt`, `code_commit.txt`, `route_probe_before.json`,
  `route_probe_after.json`.
