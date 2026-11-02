# Large-scale development evaluation v1 (2026-11-01)

This record covers the first large run of the real pipeline: 302 real job descriptions (JDs), 50 synthetic
resumes, and 150 resume × JD pairs, all sent through the HTTP API and the worker. Every number here comes from
a file in `docs/metrics/2026-11-01-large-scale-eval-v1/` or from committed labels under `evals/large_scale_v1/`.
Rates carry n and a 95% Wilson interval. The decision behind the run is ADR-047.

**This is a development set, not a holdout.** It was built and scored at the same time. All labels were made by
models (Codex, Antigravity and Claude subagents) and then adjudicated by Claude subagents. They are not human
ground truth.

## Setup

| Item | Value |
|---|---|
| JDs | 302 public postings (Notion list 112, Greenhouse boards 90, Lever/Ashby/other 100); intern 179, new grad 92, mid 31 |
| Resumes | 50 fictional personas, 214 experiences, 8 strata (including 5 adversarial) |
| Pairs | 150 (one JD per pair, high/medium/low designed fit); the other 152 JDs were parsed only |
| Product code | unchanged; prompts parse-v3 and evidence-matcher-prompt-v4; model `openai/gpt-oss-20b` |
| Embeddings | Gemini `gemini-embedding-2` |
| Harness | `scripts/large_eval/` (driver, extractor, scorer, retrieval check, scale test) |

### Provider periods

The LLM provider changed during the run, at the author's request. The scorer separates the periods.

| Period (UTC) | LLM route | Used for |
|---|---|---|
| until 2026-11-02 02:14 | Groq free tier, direct | 91 first parse attempts |
| 02:14–03:49 | OpenRouter, upstream chosen per request | 211 first parse attempts, the 20 first repeat parses |
| from 03:49 | OpenRouter with Allowed Providers = Groq only | **all 148 analyses**, the 20 second repeat parses |

On OpenRouter without pinning, four identical parser requests went to four different upstreams (DekaLLM,
Darkbloom, AkashML, Parasail), with output lengths from 200 to 832 tokens. That is why the analyses waited for the
Groq pin. The 11 driver records made before the pin (18 analysis runs in the database) are kept in
`analysis_attempts_before_groq_pin.jsonl` and
are excluded from the matcher numbers (`score.py --analysis-state`).

## Parser

Source: `score.json` → `parser`. Scored on the 302 primary jobs; the 40 repeat jobs are used only for determinism.

| Metric | Result |
|---|---|
| First attempt succeeded | 271/302 = 89.7% (85.8–92.7) |
| … Groq free tier period | 67/91 = 73.6% (63.8–81.6) |
| … OpenRouter mixed period | 204/211 = 96.7% (93.3–98.4) |
| Succeeded after the driver's retries | 293/302 = 97.0% (94.4–98.4) |
| Failed runs by code (all attempts) | `PARSER_FAILED` 133, `PARSER_OUTPUT_INVALID` 8 |
| Requirements per successful parse | p50 10, p95 26, max 46 |
| Latency of successful parses | p50 3.45 s, p95 11.6 s |

Against the adjudicated parser labels (293 JDs with a successful parse, 4,969 labeled requirements, exact text match):

| Metric | Result |
|---|---|
| Precision | 2,865/3,410 = 84.0% (82.8–85.2) |
| Recall | 2,865/4,969 = 57.7% (56.3–59.0) |
| F1 | 0.684 |
| Category correct on matched requirements | 83.2% (81.8–84.5) |
| Normalized skill exactly equal | 56.5% (54.7–58.4) |
| Recall: education / nice_to_have / must_have / responsibility | 75.7% / 80.5% / 60.6% / 44.0% |

What the failures were (from direct probes of the exact product payload, see `driver_state.jsonl` and ADR-047):

- In the Groq free-tier period the surviving worker log (it covers only the last stack session; earlier sessions'
  logs were overwritten) shows 210 HTTP 429, 13 HTTP 413, 19 HTTP 400 and 82 HTTP 200 responses from Groq
  (`worker_log_counts.json`). The 429s
  come from the free tier's daily cap of 200,000 tokens. The product's `PARSER_FAILED` code does not say which HTTP
  status caused it.
- One 455-line JD needs 10,853 tokens in one request, above the free tier's 8,000 tokens per minute (HTTP 413). The
  parser has no input-size guard or chunking.
- One 4-line JD made the model return an empty requirement list, which the strict schema (`minItems: 1`) rejects
  (HTTP 400). There is no non-error outcome for "this posting has no requirements".

**Determinism** (`score.json` → `parser.determinism`), text-set Jaccard between two successful parses of one JD:

| Comparison | n | Median Jaccard | Identical sets | Median count difference |
|---|---|---|---|---|
| Repeat vs repeat, same pinned upstream | 19 | 0.84 | 8/19 = 42.1% (23.1–63.7) | 1 (max 40) |
| Original (mixed upstreams) vs repeat | 18 | 0.57 | 2/18 = 11.1% (3.1–32.8) | 2 (max 18) |

Even on one upstream at temperature 0.1, fewer than half of the re-parsed JDs gave the same requirement set.

## Matcher (148 pairs, Groq-pinned period only)

Source: `score.json` → `matcher`. One analysis per pair, no retries were needed for rate limits (0/148 rate-limited).

| Metric | Result |
|---|---|
| Analyses succeeded | 59/148 = 39.9% |
| `MATCHER_OUTPUT_INVALID_CONTRACT` | 60 |
| `MATCHER_PROVIDER_FAILED` | 28 |
| `MATCHER_OUTPUT_INVALID_SCHEMA` | 1 |
| Latency of successful analyses | p50 6.6 s, p95 14.8 s |
| Output tokens of successful analyses | p50 498, p95 784 (cap 800) |

**Success by number of parsed requirements** (the main finding):

| Requirements | Succeeded |
|---|---|
| 1–5 | 29/31 = 93.5% (79.3–98.2) |
| 6–10 | 23/40 = 57.5% (42.2–71.5) |
| 11–15 | 7/34 = 20.6% (10.4–36.8) |
| 16–20 | 0/24 = 0% (0–13.8) |
| 21+ | 0/19 = 0% (0–16.8) |

The matcher sends all requirements in one call with an 800-token output cap. At 16 or more requirements no analysis
succeeded. The parser's median is 10 requirements, so a typical real posting sits where about half of the analyses fail.

**What `MATCHER_PROVIDER_FAILED` meant here.** All 417 OpenRouter responses in the worker log were HTTP 200 (`worker_log_counts.json`), and
these failures took 11.6–23.6 s, so they were not timeouts. A probe showed that when Groq's server-side JSON-schema
check rejects the model's output, OpenRouter returns HTTP 200 with `finish_reason: "error"`, no content, and
"Upstream error from Groq: Parsing failed". The adapter needs string content, so it reports a provider failure.
Called directly, Groq returns HTTP 400 `json_validate_failed`, which the adapter also maps to
`MATCHER_PROVIDER_FAILED`. So the code means the same on both routes, but it labels a model-output contract failure
as a provider failure. Response bodies were not logged per run, so the 28 failures are consistent with this cause,
not proven one by one.

**Against the adjudicated matcher labels** (only the 59 successful analyses, 335 requirements):

| Metric | Result |
|---|---|
| Coverage class exact (full / partial / gap) | 285/335 = 85.1% (80.9–88.5) |
| Recall of labeled full matches | 6/21 = 28.6% (13.8–50.0) |
| Recall of labeled partial matches | 0/33 = 0% (0–10.4) |
| Recall of labeled gaps | 279/281 = 99.3% (97.4–99.8) |
| Over-claim rate | 6/335 = 1.8% (0.8–3.9) |
| Under-claim rate | 44/335 = 13.1% (9.9–17.2) |
| Labeled gap shown as positive | 2/281 = 0.7% (0.2–2.6) |
| Positive citations pointing at a labeled evidence experience | 8/13 = 61.5% (35.5–82.3) |

The matcher is conservative: it almost never claims a skill the labels call a gap, and it misses most labeled
positives. The scored subset is biased toward small JDs, because only those succeeded.

**Evidence guarantee.** In the pinned period the database stored 13 positive matches (11 matched, 2 partial). None
lacked an experience, a non-blank quote, or `quote_valid = true` (`evidence_guarantee_check.txt`, a SQL check on
the evaluation database before it was deleted). The adversarial resumes, which include
prompt-injection text, had 0/15 over-claims (0–20.4%).

## Retrieval (offline, product retrievers, stored vectors)

Source: `retrieval_m1.json`, `retrieval_m2.json`. Recall@5 of the labeled supporting experience for labeled positive
requirements.

| Round | Positives | Lexical recall@5 | Hybrid recall@5 | Found only by hybrid | Missed by both |
|---|---|---|---|---|---|
| M1 | 171 | 60.8% | 74.9% | 24 | 43 |
| M2 | 188 | 52.1% | 70.7% | 35 | 55 |

Lexical never found an experience that hybrid missed. Each resume has 4–8 experiences, but the retrievers return
about 2 candidates on average (mean 2.0 hybrid in M1), so recall@5 is not automatic. During the OpenRouter-period
analyses, 0 of 1,867 requirement retrievals in the worker log fell back to lexical (the product logs a warning
when it does).

## CV import (fake model, no LLM)

Source: `score.json` → `cv_import`. The 50 resumes were rendered to Markdown and DOCX and imported.

| Format | Experiences recovered as separate drafts | CVs with the right draft count | Skills extracted |
|---|---|---|---|
| Markdown | 214/214 = 100% (98.2–100) | 50/50 | 0 |
| DOCX | 0/214 = 0% (0–1.8) | 0/50 (always 1 draft per CV) | 0 |

DOCX import collapses the whole resume into one draft, so a DOCX user must split it by hand.

## Scale and reliability (fake providers, separate stack)

Source: `scale_db_metrics.txt`, `scale_driver_summary.json`, `scale_reads_idle.json`. 50 users × 150 jobs on one
laptop, worker with 2 processes × 4 threads. These numbers measure the system, not the model.

| Metric | Result |
|---|---|
| Parse runs succeeded | 7,550/7,550 (7,500 jobs + 50 idempotency probes) |
| Analysis runs succeeded | 7,500/7,500 |
| Parse time created → finished | p50 0.27 s, p95 1.44 s |
| Analysis execution time (started → finished) | p50 1.19 s, p95 3.50 s |
| Analysis backlog drain | 7,500 runs in 1,501 s wall time (about 5 per second) |
| Idempotency checks | 150/150 passed (50 same-key parse, 50 same-key analysis, 50 expected 409s) |
| Read endpoints, idle, sequential (6 endpoints × 200 calls) | p50 5.5–11.4 ms, p95 ≤ 17.3 ms |
| Read endpoints under write load | p50 about 0.5–0.6 s |

The scale driver's own 300 s poll timed out on 6,132 analyses while the queue drained. Those are a driver limit, not
failures: the database shows all 7,500 succeeded.

## Labels and agreement

| Labels | Labelers | Agreement | Adjudication |
|---|---|---|---|
| Parser (302 JDs, 20,744 candidate lines) | Codex vs Antigravity | selection κ 0.882, category κ 0.984, skill exact 0.875 | 1,526 disputes; final 5,164 requirements |
| Matcher M1 (68 pairs, 827 requirements) | Codex vs Claude | 0.860, κ 0.581 | 116 disputes; chose Claude 105, Codex 6, neither 5 |
| Matcher M2 (80 pairs, 940 requirements) | Codex vs Claude | 0.870, κ 0.674 | 122 disputes, blinded; chose Claude 93, Codex 26, neither 3 |

Codex's first M2 attempt was rejected before adjudication because it defaulted unlisted requirements to "missing"
(κ 0.213). The adjudicators favored the Claude labeler even when blinded, so the matcher labels may lean toward
Claude's reading of the rubric.

## Sensitivity: excluding the 7 JDs flagged in review

Source: `score_excluding_reviewed_jds.json`. Parser F1 0.682 (vs 0.684); matcher success 56/144; over-claim
6/320 = 1.9%; under-claim 44/320 = 13.8%. No conclusion changes.

## Not measured

- Money spent on OpenRouter and Gemini: not measured per run (the author's provider dashboards hold it).
- Which OpenRouter upstream served each parse in the mixed period: not recorded.
- Human-labeled ground truth: not available; an author spot-check is still open.
- Matcher quality on large JDs: not measurable, because no analysis with 16 or more requirements succeeded.
- One pair parse was left in `running` after the host slept and was never finished; it is excluded.

## Files

`docs/metrics/2026-11-01-large-scale-eval-v1/`:
`score.json`, `score_excluding_reviewed_jds.json`, `results_real_run.json` (all parse and analysis rows exported from
the database), `driver_state.jsonl` (every submitted attempt), `analysis_attempts_before_groq_pin.jsonl`,
`retrieval_m1.json`, `retrieval_m2.json`, `cv_import_state.jsonl`, `order_*.json`, `worker_log_counts.json`,
`evidence_guarantee_check.txt`, `scale_db_metrics.txt`, `scale_driver_summary.json`, `scale_reads_idle.json`.
