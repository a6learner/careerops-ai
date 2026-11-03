# Parser heading filter development check (2026-11-03)

This record measures ADR-050 (parse-v4 heading filter) together with ADR-049 batching
against a real provider. It follows `2026-11-02-matcher-batching-dev.md` and uses the
same dataset, labels, route and method. Every number comes from a file in
`docs/metrics/2026-11-03-heading-filter-dev/` or from the 2026-11-02 and large_scale_v1
folders it compares against.

**This is a development check, not a holdout.** The heading rule was written after
seeing large_scale_v1 over-claims, so these numbers are not held-out quality.

## Setup

| Item | Value |
|---|---|
| Code | product build as of ADR-050: batch 6, output cap 800, `evidence-matcher-prompt-v4`, `openai/gpt-oss-20b` |
| Route | OpenRouter. The author's account setting Allowed Providers = Groq (set during large_scale_v1) is not itself recorded in an artifact. Sampled probes before and after: 3/3 and 3/3 served by Groq (`route_probe_*.json`). The serving provider of each evaluation request was not recorded |
| Parse runs | the same 150 large_scale_v1 parse runs, replayed with every requirement that `is_section_heading` rejects removed (`replay_parses.py --drop-headings`) |
| Stack | fresh isolated compose project, fresh users and experiences (tag `batch2`), same environment as `../2026-11-02-matcher-batching-dev/stack_env.sh.txt`. A database check showed 214 embedding runs succeeded before analyses (console output not saved). Deleted after the run; teardown output not saved |

The replay removes 71 of the 1,804 analysed requirements. Two pairs (`r12-jd-e182b2eb9b`,
`r18-jd-f6b95a4622`) had only heading requirements. What a real parse-v4 parse would do for
them (select other lines, return no requirements, or fail) was not measured, so they were not
analysed.

**What this does and does not measure.** It reports matcher results observed with the
headings removed, compared with separate earlier runs. There was no repeated same-input control in
this stage, so differences include run-to-run variation. It does not measure how a real parse-v4 parse selects among the
remaining candidates.

## Label check of the rule

Source: `heading_filter_label_check.json` (`scripts/large_eval/heading_filter_check.py`).

| Item | Result |
|---|---|
| Source candidates removed | 2,134 of 20,744 |
| Adjudicated parser requirements removed | 1 of 5,164 ("Proficiency in one or more of the following:", a lead-in) |
| Analysed pair requirements removed | 71 of 1,804 (all listed in the file) |

## Results

Source: `score_noheadings.json`.

| Metric | batch6 (2026-11-02) | batch6 + heading filter |
|---|---|---|
| Analyses succeeded | 107/150 | 104/148 analysable (2 pairs not analysed) |
| Failure codes | 42 invalid schema, 1 provider, 1 rate-limited | 44 invalid schema |
| Requirements scored against labels | 1,098 | 1,022 |
| Coverage class exact | 920/1,098 = 83.8% | 886/1,022 = 86.7% (84.5–88.6) |
| Over-claim | 39/1,098 = 3.6% | 24/1,022 = 2.3% (1.6–3.5) |
| Under-claim | 139/1,098 = 12.7% | 112/1,022 = 11.0% (9.2–13.0) |
| Labeled gap shown as positive | 22/901 = 2.4% | 14/848 = 1.7% (1.0–2.8) |
| Latency of successful runs, p50 / p95 | 12.5 s / 28.8 s | 8.7 s / 21.5 s |

Success by requirement count in the filtered run: 1–5 31/31; 6–10 32/39; 11–15 19/36;
16–20 13/24; 21+ 9/18. The bins use the requirement counts after filtering.

The worker log (`worker_log_counts.json`) recorded:
- 40 `finish_reason=length`, 3 `finish_reason=error` and 1 malformed ID;
- 283 OpenRouter responses, all HTTP 200.

### Like-for-like

Overall rates come from different sets of successful runs, so the arms were also compared
on the pairs that succeeded in each arm, scored only on requirements every arm analysed
(`--shared-requirements-only`).

`arms_batch6_vs_noheadings_shared.json` (86 pairs, 763 requirements):

| Metric | batch6 | batch6 + heading filter |
|---|---|---|
| Over-claim | 21 | 18 |
| Labeled gap shown as positive | 12/647 | 10/647 |
| Under-claim | 82 | 77 |
| Coverage exact | 660 | 668 |

`arms_original_batch6_noheadings_shared.json` (50 pairs that succeeded in all three, 259
requirements):

| Metric | large_scale_v1 (one call) | batch6 | batch6 + heading filter |
|---|---|---|---|
| Over-claim | 5 | 8 | 3 |
| Labeled gap shown as positive | 1/218 | 5/218 | 1/218 |
| Under-claim | 33 | 32 | 28 |
| Coverage exact | 221 | 219 | 228 |

In the 2026-11-02 controls, repeat runs of one setup differed by 2–3 over-claims on 228
requirements, so these like-for-like differences are small. In both comparisons, though, every
quality metric points the same way, and the filtered run showed no sign of being worse than the
original single call. On completion: compared with unfiltered batch 6 the filter changed little
(104 against 107). The large gain over the original 59 comes mainly from batching.

`arms_batch6_vs_noheadings_all.json` repeats the 86-pair comparison over all labeled
requirements each arm analysed. It counts the heading over-claims the unfiltered run produced (24
against 18; on shared requirements only it is 21 against 18). These are observed counts from separate
runs, not an isolated filter effect.

## Evidence guarantee

Before the database was deleted, a SQL check found 82 positive matches: 80 from this run
and 2 left by the fake-provider integration tests run on the same database afterwards.
None lacked an experience, a version, a non-blank quote or `quote_valid = true`
(`evidence_guarantee_check.txt`).

## Audit

A read-only Codex audit on 2026-11-03 (`codex_audit_2026-11-03.md`) recomputed every score,
interval, percentile, comparison and count in this record and in
`2026-11-02-matcher-batching-dev.md` from the raw artifacts, and found no numerical errors. It flagged
10 places where the wording claimed more than the artifacts show:
- route pinning and embedding completion were not saved as artifacts;
- several statements implied causes that separate stochastic runs cannot isolate.

All 10 were rewritten in both records, ADR-049, ADR-050, learning notes 0056 and 0057, and the
walkthrough. The stack environment was added as `../2026-11-02-matcher-batching-dev/stack_env.sh.txt`.

## Not measured

- Parser quality of a real parse-v4 parse (recall, precision, determinism).
- Money spent.
- Held-out quality: still needs a fresh holdout.

## Files

`docs/metrics/2026-11-03-heading-filter-dev/`:
- Data and scores: `results_noheadings.json`, `driver_state_noheadings.jsonl`,
  `score_noheadings.json`.
- Comparisons: `arms_batch6_vs_noheadings_all.json`, `arms_batch6_vs_noheadings_shared.json`,
  `arms_original_batch6_noheadings_shared.json`.
- Checks and probes: `heading_filter_label_check.json`, `worker_log_counts.json`,
  `evidence_guarantee_check.txt`, `route_probe_before.json`, `route_probe_after.json`.
