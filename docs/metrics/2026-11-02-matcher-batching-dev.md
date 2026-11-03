# Matcher batching development check (2026-11-02)

This record measures ADR-048 (failure diagnostics) and ADR-049 (batches of at most 6 requirements per
matcher call) against a real provider. It reuses the large_scale_v1 dataset and labels. Every number
comes from a file in `docs/metrics/2026-11-02-matcher-batching-dev/`, or from the large_scale_v1 files it
compares against (`docs/metrics/2026-11-01-large-scale-eval-v1/`).

**This is a development check, not a holdout.** large_scale_v1 was built and scored together, its
labels were made by models, and the batch size was chosen from its token data. No result here is
held-out quality.

## Setup

| Item | Value |
|---|---|
| Code | branch `claude/matcher-reliability`; ADR-048 (`a0f840f`), ADR-049 (`0d679a8`, `0ab9f57`), logging fix `6f49592` |
| Matcher | `openai/gpt-oss-20b`, `evidence-matcher-prompt-v4`, output cap 800 tokens, one attempt per call |
| Route | OpenRouter. The author's account setting Allowed Providers = Groq (set during large_scale_v1) is not itself recorded in an artifact. Sampled probes before and after: 3/3 and 3/3 served by Groq (`route_probe_*.json`). The serving provider of each evaluation request was not recorded |
| Embeddings | Gemini `gemini-embedding-2`; 214 experiences. A database check showed all 214 embedding runs succeeded before analyses were submitted, but that console output was not saved |
| Parse runs | **Replayed, not re-parsed.** For each of the 150 pairs, the exact parse run the large_scale_v1 analysis used, with the same parse-run and requirement IDs (`scripts/large_eval/replay_parses.py`). The matcher change is therefore not mixed with parser nondeterminism, and the committed labels apply unchanged |
| Labels | union of `evals/large_scale_v1/labels/matcher/m{1,2,3,4}/final/` |
| Stack | isolated compose project `careerops-batcheval`, API and one worker (1 process × 4 threads); environment in `stack_env.sh.txt` (the key is read from `.env` at runtime). Deleted after the run; teardown output not saved |

Re-scoring the original large_scale_v1 export with this label union reproduces its `score.json`
matcher section exactly. That confirms the scoring setup.

### Runs (arms)

All arms ran on the same database and the same day. Each arm has its own driver state; the scorer keeps
only that arm's runs (`--analysis-state`).

| Arm | Pairs | Batch | Cap | How it was produced | State file |
|---|---|---|---|---|---|
| batch6 | 150 | 6 | 800 | product code as committed | `driver_state_batch6.jsonl` |
| single_today | 54 | none (`matcher-batch-1000`) | 800 | eval-only API launcher stamps the old single-call behavior (`eval_api_with_batch.py.txt`) | `driver_state_single.jsonl` |
| batch6_repeat | 54 | 6 | 800 | product code, second run | `driver_state_batch6_repeat.jsonl` |
| cap800_rerun | 43 | 6 | 800 | product code, re-run of batch6 failures | `driver_state_cap800ctl.jsonl` |
| cap1600 | 43 | 6 | 1600 | eval-only worker wrapper raises the cap (`eval_worker_cap1600.py.txt`) | `driver_state_cap1600.jsonl` |
| batch3 | 43 | 3 | 800 | eval-only API launcher stamps `matcher-batch-3` | `driver_state_batch3.jsonl` |

The 54 pairs are those that succeeded in both large_scale_v1 and batch6 (`order_both54.json`). The 43
pairs are batch6's failures (`order_failed43.json`). The host machine restarted during cap1600; 34 of
43 pairs had finished. The other 9 ran after a restart on the same database. The one run left in
`running` was never recorded by the driver, so no arm counts it.

## Result 1: with batching, most large jobs completed

Source: `score_batch6.json` and `compare_batch6_vs_large_scale_v1.json`. Success is the first
attempt, excluding rate limits (large_scale_v1 had none; batch6 had one, retried and then succeeded).

| Requirements | large_scale_v1 (one call) | batch6 |
|---|---|---|
| 1–5 | 29/31 | 29/31 |
| 6–10 | 23/40 | 33/40 = 82.5% (68.1–91.3) |
| 11–15 | 7/35 | 23/34 = 67.6% (50.8–80.9) |
| 16–20 | 0/24 | 12/24 = 50.0% (31.4–68.6) |
| 21+ | 0/20 | 9/20 = 45.0% (25.8–65.8) |
| All | 59/150 | 106/150 first attempt; 107/150 after the rate-limit retry |

Pair by pair: 52 went fail → ok, 5 went ok → fail, 54 stayed ok and 39 stayed failed. These are
separate stochastic runs on different days. The failed pairs were not re-run under the old single-call
behavior, so this does not isolate batching as the only cause. The size of the shift at 16 or more
requirements (0/44 to 21/44), together with the token arithmetic in ADR-049, makes batching the likely
main factor.

Failures in batch6, first attempt: 42 `MATCHER_OUTPUT_INVALID_SCHEMA`, 1 `MATCHER_PROVIDER_FAILED`,
1 rate-limited. There were no `MATCHER_OUTPUT_INVALID_CONTRACT` failures; large_scale_v1 had 62.

ADR-048's diagnostics show what the schema failures were. Counts are from the worker logs
(`worker_log_counts.json`); the logs are per worker session, not per arm:
- The batch6 worker session (it also served single_today and batch6_repeat) logged 38
  `finish_reason=length` (the output cap was reached), 8 `finish_reason=error` (provider-side schema
  rejection) and 3 malformed IDs.
- Output tokens per successful batch6 run: p50 823, p95 2,078. Input tokens: p50 4,362, p95 9,888.
  Latency: p50 12.5 s, p95 28.8 s (n = 107).

## Result 2: over-claiming on the same pairs

On the 54 pairs that succeeded in both runs (`compare_batch6_vs_large_scale_v1.json`, 296 labeled
requirements):

| Metric | large_scale_v1 | batch6 |
|---|---|---|
| Coverage class exact | 252/296 | 249/296 |
| Over-claim | 6/296 | 11/296 |
| Under-claim | 38/296 | 36/296 |
| Labeled gap shown as positive | 2/250 | 8/250 |
| Same verdict as large_scale_v1 | — | 258/296 = 87.2% (82.9–90.5) |

To tell a batching effect from ordinary run-to-run variation, the old single-call behavior was re-run
on the same day (`arms_common_pairs.json`). Over the 48 pairs that succeeded in all four arms (228
requirements):

| Arm | Over-claim | Gap shown as positive | Coverage exact |
|---|---|---|---|
| large_scale_v1 (one call) | 4/228 | 2/197 | 199/228 |
| single_today (one call) | 7/228 | 5/197 | 196/228 |
| batch6 | 10/228 | 8/197 | 195/228 |
| batch6_repeat | 8/228 | 7/197 | 195/228 |

The same single-call setup moved from 4 to 7 between days, and batch6 moved from 10 to 8 between two
runs. The batch-6 counts are a few higher than the single-call counts. The differences are similar in
size to the changes seen between repeat runs of one setup, but with only two runs per setup no
run-to-run distribution was estimated, so a small batching effect cannot be ruled out. In every arm, 1 to 3 of the over-claims are on heading-like text that the parser stored
as a requirement (`overclaims_on_common_pairs` in the same file).

## Result 3: the remaining failures are large jobs, and rescuing them shows more over-claiming

The 43 batch6 failures were run three more ways (`arms_failed_pairs.json`, `score_cap800ctl.json`,
`score_cap1600.json`, `score_batch3.json`):

| Arm | Succeeded | Over-claim on its successes | Gap shown as positive | Coverage exact |
|---|---|---|---|---|
| cap800_rerun (same product code, re-run) | 14/43 (13 first attempt, 1 after a rate-limit retry) | 8/221 = 3.6% | 8/184 | 195/221 |
| cap1600 | 39/43 | 52/631 = 8.2% (6.3–10.7) | 36/464 = 7.8% | 498/631 |
| batch3 | 36/43 | 48/572 = 8.4% (6.4–11.0) | 34/426 = 8.0% | 451/572 |

On the 13 pairs that succeeded in all three arms (205 requirements), over-claims were 8, 11 and 14.
These counts are themselves above the 2–4% seen on smaller jobs, and the pairs only cap1600 or batch3
rescued have higher rates still: 41/426 for cap1600 and 34/367 for batch3. Large, hard jobs over-claim
more in every arm, and most of all where the model needed long outputs. In the cap1600 arm, 8 of the 52 over-claims are on the adversarial resumes, and one
unproven claim ("Improved checkout performance by 300 percent.") was cited for 3 requirements.

Cost of the alternatives, from the same score files:
- cap1600: output tokens p50 1,946 and p95 4,909 per successful run; latency p50 17.9 s.
- batch3: input tokens p50 9,304 and p95 21,254 per successful run (instructions are repeated per
  call); latency p50 17.5 s and p95 43.3 s.

**Decision taken in this stage:** the product default stays at batch 6 with the 800 cap. Raising the
cap or shrinking batches would complete more large jobs, but on those jobs about 8% of labeled
requirements are over-claimed. Over-claiming is the project's main risk, so that trade-off is left
for the author (ADR-049).

## Evidence guarantee

Before the database was deleted, a SQL check found 371 positive matches across all arms (11
single-call, 108 batch-3, 252 batch-6 including cap1600 and cap800_rerun). None lacked an experience,
a version, a non-blank quote or `quote_valid = true` (`evidence_guarantee_check.txt`). This checks that
the stored fields are complete, not that the evidence is semantically right. The over-claims above are
semantic: each cites a real, validated quote that the labels judge too weak for the requirement.

## Problems found and fixed during the run

- The JSON log formatter only emits allowlisted fields, so ADR-049's `batch_index` and `batch_count`
  were dropped. Fixed in `6f49592`, after the batch6 run, so the batch6 logs have no batch positions.
- Worker logs were written per session as appended UTF-8. The large_scale_v1 lesson about overwritten
  UTF-16 logs did not recur.

## Not measured

- Money spent: not measured per run.
- Per-batch output tokens: only run totals are stored. Per-batch figures in the ADR are estimates.
- Whether the 8% over-claim rate on large jobs holds outside this development set: not measured.
  It needs a fresh holdout.
- Human-labeled ground truth: still not available.

## Files

`docs/metrics/2026-11-02-matcher-batching-dev/`:
- Data and states: `results_all_runs.json` (all analysis rows of the evaluation database),
  `driver_state_{batch6,single,batch6_repeat,cap800ctl,cap1600,batch3}.jsonl`,
  `pair_requirements_all.json`, `order_analysis.json`, `order_both54.json`, `order_failed43.json`.
- Scores and comparisons: `score_{batch6,cap800ctl,cap1600,batch3}.json`,
  `compare_batch6_vs_large_scale_v1.json`, `arms_common_pairs.json`, `arms_failed_pairs.json`.
- Logs, probes and checks: `worker_log_counts.json`, `evidence_guarantee_check.txt`,
  `route_probe_{before,after}.json`, `route_probe.py.txt`.
- Eval-only launchers: `eval_api_with_batch.py.txt`, `eval_worker_cap1600.py.txt`.

Harness: `scripts/large_eval/replay_parses.py`, `compare_matcher_runs.py`, `compare_matcher_arms.py`,
plus the existing driver, extractor and scorer.
