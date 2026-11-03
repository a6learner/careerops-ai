# Real-Data Walkthrough Test Record - 2026-10-31

## Scope

This record captures one walkthrough of the code at `ed63fb9`
(`claude/ui-and-product-polish`, clean tree) and a re-check after the ADR-046
parser fix (Part 3). The first two parts are:

1. The normal quality gates with deterministic fake providers.
2. One exploratory run of the full pipeline with **real providers** (Groq
   `openai/gpt-oss-20b` for parsing and matching, Gemini `gemini-embedding-2` for
   embeddings) on the author's real one-page CV and three real internship job
   descriptions (IDEMIA, AspenTech, ModMed).

The real-provider part is a small, one-off observation, not an evaluation. It has
no labeled ground truth set, no holdout, and n = 3 job descriptions. Raw CV text,
raw model responses and result JSON were kept outside the repository. Personal CV
content is described structurally below and not quoted.

## Part 1: Fake-provider quality gates

| Gate | Result |
|---|---|
| `pytest` (unit, fake providers) | 449 passed, 28 skipped (all 28 skips are integration-gated) |
| `ruff check .` | pass |
| `mypy` (strict, 145 files) | pass |
| `lint-imports` | 2 contracts kept, 0 broken |
| Frontend `lint`, `typecheck` | pass |
| Frontend `vitest` | 19 files, 43 tests passed |
| `alembic upgrade head` + `alembic check` on a blank pgvector DB | pass, no drift |
| Integration (`CAREEROPS_RUN_INTEGRATION=1`, isolated Postgres/Redis) | 22 passed, 4 failed, 2 skipped (`test_groq_live`, `test_worker_e2e`) |
| Rerun of the 4 failures with `127.0.0.1` URLs | 3 passed, 1 failed (`test_dashboard_summary_cache_invalidation_and_archived_scope`) |
| Full-stack browser acceptance (`scripts/local_full_stack_acceptance.ps1 -RunId walkthrough-20261031`) | migration passed, frontend non-root (uid 1000), Playwright 2/2 passed (core loop, project records), browser 23.2 s, cleanup passed |

Host notes, not product defects:

- pytest needed `--basetemp` inside the session scratch directory because the
  default system temp folder was not writable in this sandbox.
- With `localhost` URLs on this Windows host, Redis connections exceeded the
  app's 0.2 s `redis_socket_timeout_seconds`. All four first-pass failures were
  `redis.exceptions.TimeoutError`. After switching to `127.0.0.1`, one dashboard
  cache test still timed out connecting to Redis. It is recorded as
  host-sensitive. No CI result is claimed.
- Integration tests took 22 s to 67 s each on this host (781 s total).
- Script bug: the acceptance script's default `RunId`
  (`yyyyMMddTHHmmssZ`) contains uppercase letters. Docker Compose v5.4.0 rejects
  that as a project name, and PowerShell does not apply the parameter's own
  `ValidatePattern` to defaults. Passing a lowercase `-RunId` works. The default is
  now lowercased in this script and in `local_migration_rollback_drill.ps1` and
  `local_read_endpoint_benchmark.ps1`, which had the same default.

## Part 2: Real-provider walkthrough

### Setup

- Isolated Compose project `careerops-realtest` (Postgres on 15430, Redis on 16330).
  API (uvicorn) and worker (Dramatiq) ran from the venv with
  `LLM_PROVIDER=groq`, `EVIDENCE_MATCHER_PROVIDER=groq`, `RUN_REAL_MATCHER_WORKER=1`,
  `EMBEDDING_PROVIDER=gemini`, `RUN_EMBEDDING_INTEGRATION=1`, `ANALYSIS_RATE_LIMIT=20`.
- Two users, same CV, same three job descriptions:
  - **Condition A (CV import):** upload the PDF through `/api/v1/cv-imports`, confirm
    every generated draft unchanged.
  - **Condition B (manual entry):** the same CV typed in by hand as six Experiences
    (one internship, two research roles, two projects, education), with skills.

### Finding 1: CV import produced one draft for the whole CV

pypdf extracted 4,441 characters with **zero blank lines**. `extract_experience_drafts`
splits on `"\n\n"`, so the import produced **1 draft** titled with the author's name,
holding the whole CV as its description and no skills. Extraction also added a space
before hyphens (`duplicate -call`, `LLM -judged`). That breaks exact-substring
citations for any quote that spans those words.

### Finding 2: the real parser failed most full job descriptions

Before any patch, the real parser was run on the three full job descriptions 17
times in total (6 through the worker, 11 through direct adapter calls). It returned
HTTP 200 every time, and **2 of 17 passed grounding validation** (both IDEMIA, through
direct calls). Every worker run ended `PARSER_OUTPUT_INVALID`. A 3-line toy job
description passed 1/1.

Root causes, confirmed from the raw responses:

1. **Duplicate `candidate_id`.** The output schema allows one `skill_normalized` per
   source sentence. For sentences that list several skills ("Java, Python, C++, or
   similar"; "TCP/IP, UDP, DNS, …"; "Microservices, Java, MySQL and Angular"), the
   model emitted the same sentence several times. `build_grounded_requirements`
   rejects any duplicate, which fails the whole run. All 9 repeated direct calls
   failed this way (duplicates per response: 1 to 5).
2. **The sentence splitter breaks on dots inside tokens.** "GPA of 3.5 or higher"
   became `"…GPA of 3."` plus `"5 or higher and experience with Microservices…"`,
   and "(e.g. Kafka)" became `"…streaming platform experience (e."`.
3. **Failed parse runs keep no diagnostics.** `input_tokens`/`output_tokens` are null
   and no log line records the reason. The matcher path does log rejected-output
   diagnostics.

The earlier parser evaluation (12 synthetic cases, 31 requirements, parse-v2 12/12
completed, `2026-09-08-groq-requirement-eval-summary.md`) had no multi-skill list
sentences, so it could not catch this.

### Finding 3: matcher results with an experiment-only parser patch

To observe the matcher, a **scratchpad-only** worker entry point kept the first
occurrence of each duplicated `candidate_id`. Product code was not changed.
Results:

- Parsing was nondeterministic. IDEMIA gave 16, 17, 10 and 17 requirements across
  four successful calls. AspenTech kept only 3 requirements. The "Your Impact"
  responsibilities were dropped.
- Analyses submitted back to back: 1 succeeded, 4 failed
  `MATCHER_PROVIDER_RATE_LIMITED` (Groq HTTP 429), 1 failed
  `MATCHER_OUTPUT_INVALID_CONTRACT`. The matcher uses `max_attempts=1` and Dramatiq
  `max_retries=0`, so a 429 ends the run.
- Analyses resubmitted 70 s apart: 4 of 6 succeeded. **IDEMIA failed
  `MATCHER_OUTPUT_INVALID_CONTRACT` in both conditions (10 and 17 requirements).**
  The single matcher call did not return exactly one verdict per requirement.

Successful runs (latency and tokens as reported by the run row):

| Condition | Job | Reqs | Latency ms | In / out tokens | Matched | Partial | Insufficient | Missing | Validator downgrades |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A (CV import) | AspenTech | 3 | 3,639 | 2,243 / 463 | 2 | 0 | 0 | 1 | 0 |
| A (CV import) | ModMed | 6 | 5,690 | 2,716 / 679 | 2 | 0 | 0 | 4 | 0 |
| B (manual) | AspenTech | 3 | 3,278 | 2,697 / 292 | 0 | 0 | 0 | 3 | 0 |
| B (manual) | ModMed | 5 | 5,589 | 2,981 / 626 | 2 | 0 | 1 | 2 | 1 |

Author-visible observations (the author has not formally labeled them):

- **No unsupported positive claim was observed.** Every `matched` verdict quoted an
  education entry, the GPA, or the skills line, and all quotes passed validation.
- **Partial was never used** (0 of 17 verdicts), consistent with the holdout's
  partial recall of 0/2.
- **Likely false negatives:**
  - In condition B, "Proficiency with one or more of: C, C++, Java, Python,
    JavaScript" was `missing`, although four Experiences list Python as a skill.
    The parser reduced that requirement to `skill_normalized = "c"`.
  - "Experience with Claude, Codex, Cursor or similar AI development tools" was
    `missing` in both conditions, despite an LLM-runtime/MCP internship and this
    project.
- **How evidence is shaped changed the results.** The single CV-blob draft (A)
  matched the language requirement through its skills line. The cleaner manual
  Experiences (B) did not.
- **Confidence was uninformative.** `missing` verdicts carried confidence 1.0 in
  one run and 0.0 in another.
- One condition-B citation was downgraded by the validator to
  `insufficient_evidence` (`validation_failure_count = 1`).

### Provider usage

About 24 Groq chat requests (parser and matcher, including diagnostics and 429s)
and Gemini embedding batches for 14 Experiences plus queries. Cost: not measured.

## Part 3: After the parser fix (ADR-046, parse-v3)

Same three job descriptions, real Groq, product code with ADR-046 applied and no
experiment patch:

- Direct `parse()` + `validate_parser_output`: **7 of 7 passed**.
  - IDEMIA: 17, 18, 16 requirements.
  - AspenTech: 16, 16 (was 3 with the experiment patch, because the old splitter and
    merge dropped most lines).
  - ModMed: 6, 8.
  - One extra attempt was rejected by Groq with HTTP 429 and is not counted.
- Unpatched worker, condition B (manual Experiences), analyses submitted 75 s
  apart:
  - parse runs: 3 of 3 succeeded (16, 14, 5 requirements);
  - IDEMIA analysis: succeeded, 12,258 ms, 4,999 / 793 tokens, **16 of 16
    `missing`**;
  - AspenTech analysis (14 requirements): failed `MATCHER_OUTPUT_INVALID_CONTRACT`;
  - ModMed analysis: succeeded, 3,981 ms, 3,191 / 790 tokens; 1 matched, 1 partial,
    3 missing.
- With parsing fixed, the main remaining problem is matcher under-claiming. The
  IDEMIA run marked "Java, Python, C++, or similar" and "Previous internship or
  project experience in software development" as `missing`, although several
  manual Experiences support both. The single matcher call still breaks its
  one-verdict-per-requirement contract on some 10+ requirement jobs.

## What this record does not show

- Accuracy, recall or precision on real data. There is no labeled set; n = 3 job
  descriptions; one CV.
- Production behavior, throughput or cost.
- Matcher quality beyond these few runs. Part 3 has 2 successful unpatched
  analyses, which is enough to show the under-claiming pattern but not to measure
  it.
