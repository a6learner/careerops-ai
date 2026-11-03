# ADR-046: Requirement Parser Contract Hardening (parse-v3)

## Status

Accepted by the author on 2026-10-31 (merge option chosen over a schema change).
Implemented and verified locally.

## Context

The 2026-10-31 real-data walkthrough
(`docs/metrics/2026-10-31-real-data-walkthrough-test-record.md`) ran the Groq
parser on three real internship job descriptions. Only 2 of 17 full-description
parses passed. Every response was HTTP 200 and schema-valid. The failures came
from the parser's own contract:

1. **Duplicate candidate IDs.** The output schema has one `skill_normalized` per
   source sentence. For a sentence that lists several skills ("Java, Python, C++,
   or similar"), the model returned that sentence once per skill. ADR-012 treated
   any duplicate ID as invalid, so one such sentence failed the whole run.
2. **Fragmenting splitter.** The candidate regex ended a sentence at every `.`, so
   "GPA of 3.5 or higher and experience with Microservices…" became `"…GPA of 3."`
   plus `"5 or higher and experience with Microservices…"`, and "(e.g. Kafka)"
   became `"(e."`.
3. **No failure diagnostics.** A rejected parse stored no tokens and logged no
   reason, so cost and cause were invisible.

The 12-case synthetic development set (ADR-013) had no multi-skill list sentences,
so it could not catch the first two issues.

## Decision

- **Merge repeated candidate IDs** into one requirement. The requirement text is
  still sliced from the source sentence. The first category and the first
  non-blank skill are kept, and a blank skill becomes `null`. Unknown candidate IDs
  still fail the run. The prompt now asks for each ID once, using the first named
  skill.
- **Splitter:** a `.` between two digits, or inside `e.g.`, `i.e.`, `etc.`, `vs.`,
  `incl.`, `approx.`, does not end a candidate. Newlines and other terminators
  behave as before. Candidates made only of punctuation are dropped.
- **Diagnostics:** `ParserOutputValidationError` carries a reason
  (`no_candidates`, `invalid_schema`, `unknown_candidate`, `ungrounded_output`) and
  provider token counts. The execution service logs
  `requirement_parser_output_rejected` with the reason and stores tokens on the
  failed parse run.
- `PARSE_PROMPT_VERSION` becomes `parse-v3`. Runs created earlier keep their
  recorded `parse-v2` label.

No migration, API field or database constraint changes.

## Alternatives considered

- **Add a `skills_normalized text[]` column and API field.** This keeps every skill
  named in a sentence. Not chosen now because it needs a migration and a public
  API change. The other skill names still appear in the requirement text, which
  the lexical retriever and the matcher both read. It remains the upgrade path.
- **Keep rejecting duplicates and only change the prompt.** Not chosen: the
  instruction already said "once", and the model ignored it on most real inputs.
- **Repair by re-asking the model.** Not chosen: it adds cost and latency for a
  case that is safe to merge, because no model-written text is persisted.

## Consequences

- Real job descriptions now parse instead of failing closed.
- Only the first named skill is stored per sentence. A requirement like "Java,
  Python, C++" is stored with `skill_normalized = "java"`, so exact-skill
  retrieval boosts only Java.
- Merging is not weaker grounding: the persisted text and span still come from
  the source, and unknown IDs are still rejected. The category comes from the
  model's first emission of that sentence.
- An `etc.` that really ends a sentence mid-line no longer splits it from the next
  sentence on that line. This was accepted as a lesser error than fragments.

## Verification or evidence

- Unit tests in `tests/test_groq_requirement_parser.py`:
  - splitter: decimals, abbreviations, punctuation-only lines;
  - merging repeats, blank skill becomes `null`;
  - failure reason and tokens for unknown IDs and invalid schema.
- `tests/test_parse_run_execution.py`: the rejection is logged with its reason and
  the failed run stores tokens.
- Full suite: 453 passed, 28 skipped; ruff, mypy strict and import-linter pass.
  Parse, analysis and latest-run integration tests passed against isolated
  Postgres/Redis.
- Real Groq on the same three job descriptions after the change: 7 of 7 direct
  parses passed (16–18, 16, 6–8 requirements), and 3 of 3 parse runs succeeded
  through the unpatched worker. Details are in the walkthrough test record.
