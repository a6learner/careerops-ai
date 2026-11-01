# 0053 Parser Contract Hardening (parse-v3)

## What Changed

- The Groq parser merges repeated `candidate_id`s into one requirement instead of
  rejecting the whole parse. The first category and the first non-blank skill win.
- The sentence splitter no longer splits on dots inside decimals (`3.5`) or common
  abbreviations (`e.g.`, `i.e.`, `etc.`, `vs.`).
- A rejected parse logs `requirement_parser_output_rejected` with a reason and
  stores provider token counts on the failed run.
- `PARSE_PROMPT_VERSION` is now `parse-v3` (ADR-046).

## Why It Exists

A first run on real job descriptions passed 2 of 17 parses. Real postings list
several skills in one sentence ("Java, Python, C++"). The model then returned the
same sentence once per skill, and the old duplicate check failed the whole run.
The synthetic evaluation set never had sentences like that.

## Failure Modes It Prevents

- A single multi-skill sentence wiping out the parse of an otherwise valid job.
- Requirement text split into meaningless fragments such as `"5 or higher and…"`.
- Silent failures: no record of why a parse failed or what it cost.

## Why Merging Is Still Grounded

The model never writes requirement text. It only picks sentence IDs, and the
stored text and span always come from the original job description. A repeated ID
points to the same real sentence, so merging can't introduce invented text. An ID
that doesn't exist is still rejected.

## How It Was Verified

- New unit tests cover the splitter, merging and the failure reasons with tokens.
- Integration tests for parse runs pass against isolated Postgres.
- Real Groq on the same three job descriptions: 7 of 7 direct parses passed and
  3 of 3 worker parse runs succeeded
  (`docs/metrics/2026-10-31-real-data-walkthrough-test-record.md`).

## What The Author Must Understand

- Level 1: the difference between *rejecting* model output and *repairing* it, and
  why repairing is safe here (no model-written text is persisted) when it would not
  be safe for evidence quotes.
- Level 1: why a synthetic evaluation set can pass 12/12 while real inputs fail, and
  why the evaluation data has to look like real input.
- Level 2: how `extract_source_candidates` protects dots, and why the version label
  changed even though no database field did.

## Knowledge Check

1. Why does merging two outputs that share a `candidate_id` not weaken grounding,
   while accepting a quote that is "almost" a substring would?
2. A sentence names Java, Python and C++. Which skill is stored, and what does that
   mean for exact-skill retrieval?
3. What would `skills_normalized text[]` change in the database, the API and the
   retriever, and why was it deferred?
4. Where do you look to find out why, and at what token cost, a parse run failed?
5. Why bump `PARSE_PROMPT_VERSION` when the database schema did not change?
