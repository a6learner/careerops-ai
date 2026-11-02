# ADR-047: Large-Scale Development Evaluation (large_scale_v1)

## Status

Accepted by the author on 2026-11-01. The plan was approved: free-tier providers with a sampled matcher, model labels from two independent labelers plus adjudication, data committed as a development set, and local commits only. The run finished on 2026-11-02 (UTC); results are in `docs/metrics/2026-11-01-large-scale-eval-v1.md`.

Amended during the run at the author's request: LLM calls moved from the Groq free tier to OpenRouter, pinned to the Groq upstream, and the Gemini key was moved to a paid tier (each with a $5 cap set by the author). This was a configuration change only.

## Context

The 2026-10-31 walkthrough (n = 3 JDs, 1 CV) found parser rejections (fixed by ADR-046), matcher under-claiming, contract failures on large jobs, and 429s ending runs. That sample was too small to measure any of these problems. The earlier evaluation sets are small and synthetic (12 parser cases, 8 matcher holdout cases), and their holdouts are closed (ADR-022, ADR-029).

## Decision

- **Data:**
  - 302 real, public job descriptions:
    - the author's Notion job list, whose posting text was fetched from the public pages;
    - public Greenhouse, Lever and Ashby board APIs.
  - 50 fictional resumes (214 experiences) in 8 strata. The adversarial stratum includes prompt injection, plans, negations and unproven metrics.
  - 150 resume × JD pairs: high, medium and low designed fit, with each JD used once.
- **Split:** development only. The set is built and scored at the same time, so it must never be used as a holdout. A future holdout must be freshly collected.
- **Labels:** model labels, never presented as human ground truth.
  - **Parser:** Codex and Antigravity independently, then Claude adjudication.
  - **Matcher** (rubric v2, ADR-027): Codex and Claude subagents independently, then Claude adjudication.
  - Agreement (Cohen's κ) and adjudication direction are reported.
  - Labels are committed before any matcher output for those pairs exists. Parser labels are committed before scoring.
- **Product path:** real runs go through the HTTP API and the Dramatiq worker (`scripts/large_eval/drive_pipeline.py`).
  - Product code, prompts, schemas and API contracts are unchanged.
  - The tooling lives in `scripts/large_eval/`.
- **Providers:** model `openai/gpt-oss-20b` and Gemini `gemini-embedding-2`.
  - Started on the Groq free tier. After the author's change, LLM calls went to OpenRouter through the same OpenAI-compatible adapter (`CAREEROPS_LLM_BASE_URL`, key from `OPENROUTER_API_KEY`).
  - OpenRouter first routed each request to a random upstream, so the author pinned Allowed Providers to Groq. All 148 scored analyses ran in that pinned period. Analyses from earlier periods are archived and excluded from scoring.
  - The scorer reports parser results by provider period.
  - The driver paces requests, checkpoints every step, retries quota failures with a new idempotency key, records the first attempt and every retry, and stops retrying a key after 20 attempts.
- **Matcher label rounds:** M1 (68 pairs) and M2 (80 pairs), each committed before any analysis of those pairs. M2 disputes were adjudicated blind (hash-ordered options, rationales hidden).
- **Determinism:** 20 seeded parser-only JDs are parsed twice more (`repeat`, `repeat2`); the pinned-host pair is the clean comparison.
- **Free stages:**
  - CV import of the rendered Markdown and DOCX resumes, which uses no model.
  - A fake-provider scale run: 50 users × 150 jobs, 7,500 parse and 7,500 analysis runs.
- **Reporting:** every rate carries n and a 95% Wilson interval. Anything not measured is written as "not measured".

## Alternatives considered

- **Paid provider tiers.** First rejected to stay on the free tier; adopted mid-run by the author once the free-tier daily caps stretched the run to several days.
- **Unpinned OpenRouter routing.** Rejected: identical requests went to four different upstreams with output lengths from 200 to 832 tokens, which would mix hosts inside one measurement.
- **Author-labeled ground truth.** Not feasible at this size. An author spot-check sample remains open.
- **Running the matcher on every resume × JD pair (7,500).** Not feasible on the free tier.
- **Reusing the existing frozen sets.** Not allowed: their holdouts are closed, and they are too small and synthetic.

## Consequences

- Free-tier limits shaped the first part of the run and are themselves findings:
  - Groq allows 200,000 tokens per day and 8,000 tokens per minute.
  - Gemini allows 1,000 embedding requests per day.
  - A failed embedding run is permanent for that experience version.
- Parser results mix provider periods; they are reported per period. The matcher results come from one period.
- The matcher's quality numbers cover only analyses that succeeded, which are mostly small JDs.
- Model labels can share biases with the system under test. Cross-family labeling and the reported κ limit this risk but do not remove it.
- Each resume has only 4–8 experiences. The retrievers returned about 2 candidates on average, so recall@5 still separates lexical from hybrid retrieval, but a larger experience library would be a harder test.

## Verification or evidence

- Dataset and manifest: `evals/large_scale_v1/`.
- Committed labels:
  - parser: `evals/large_scale_v1/labels/parser/`;
  - matcher: `evals/large_scale_v1/labels/matcher/`.
  - matcher M2: `evals/large_scale_v1/labels/matcher/m2/` (README explains the rejected first Codex attempt).
- Results: `docs/metrics/2026-11-01-large-scale-eval-v1.md` and the artifacts in `docs/metrics/2026-11-01-large-scale-eval-v1/`.
