# ADR-050: Parser Heading Filter (parse-v4)

## Status

Implemented and verified locally on 2026-11-03, under the author's standing goal to
fix worse results found while testing the matcher-reliability stages. It enforces the
existing parser rule "Ignore headings" (ADR-046 prompt) in code. The author has not
yet reviewed this ADR.

## Context

The ADR-049 real-provider check
(`docs/metrics/2026-11-02-matcher-batching-dev.md`) showed more over-claiming once
batching let large jobs succeed.
- Same-day controls placed most of the change within run-to-run variation.
- But in every arm, some gap-to-positive claims were on text that is not a
  requirement at all: "Requirements:", "Experience:", "FRONTEND PROGRAMMER
  INTERN", "`<h3>What You'll Need</h3>`", "As a core member of the team, you
  will:".
- The parser prompt already says to ignore headings, but the model selected
  them anyway: 71 of the 1,804 requirements of the 150 analysed pairs.
- The matcher then cited an unrelated quote for some of them.

## Decision

- **Filtering.** `GroqRequirementParser.parse` sends only
  `selectable_candidates(extract_source_candidates(text))` to the model.
  `is_section_heading` drops a candidate when, after removing HTML tags, it:
  - is empty markup;
  - ends with a colon (a lead-in whose content is on the next lines);
  - is wrapped in an HTML `<h1>`–`<h6>` tag;
  - is a known section title (for example "Requirements", "Qualifications",
    "Responsibilities", "What you'll do"); or
  - is a 2–6 word all-caps line without commas.
- **IDs and spans.** Candidate IDs and spans are unchanged. Labels, grounding
  and span checks keep working, and the model simply never sees heading
  candidates.
- **No candidates left.** A posting with only headings gets the existing
  `NO_CANDIDATES` parser failure, with no provider call.
- **Versioning.** `PARSE_PROMPT_VERSION` is now `parse-v4`. The prompt text is
  unchanged, but the candidate set the model sees is different.

## Alternatives considered

- **Changing the prompt.** The prompt already asks for this, and the model does
  not reliably follow it.
- **Filtering after the model answers.** The model would still spend output on
  headings, and its category choices for neighbouring lines would be made with
  heading noise in view.
- **A learned classifier.** Too heavy for the problem. The rule is short,
  testable and checked against the labels.

## Consequences

- **Real requirements lost.** One of 5,164 adjudicated parser labels is
  dropped: "Proficiency in one or more of the following:", a lead-in whose items
  are labeled on the following lines.
- **Fewer candidates.** The rule removes 2,134 of 20,744 source candidates in
  large_scale_v1, so parser prompts are shorter.
- **Jobs with only headings.** Two analysed pairs had only heading
  requirements, so a real `parse-v4` parse would choose different lines for
  them. The development check could not replay them and left them out.
- **Not measured.** How a real `parse-v4` parse selects among the remaining
  candidates; parser recall has not been re-scored with a fresh parse.

## Verification or evidence

- `tests/test_groq_requirement_parser.py`:
  - Heading and non-heading cases, including "Requirements: 2+ years of Go"
    and "SQL" kept.
  - Original candidate IDs and spans are kept.
  - Only headings gives `NO_CANDIDATES` without a call.
- Label check: `docs/metrics/2026-11-03-heading-filter-dev/heading_filter_label_check.json`
  (`scripts/large_eval/heading_filter_check.py`).
- Real-provider development check: `docs/metrics/2026-11-03-heading-filter-dev.md`.
  - On the 50 pairs that succeeded in the original run, batch 6 and batch 6
    with the filter, scored on the same 259 requirements, over-claims were 5,
    8 and 3.
  - Labeled gaps shown as positive were 1, 5 and 1.
  - Coverage exact was 221, 219 and 228.
- Gates on 2026-11-03:
  - `ruff check .`, `mypy --strict src` and `lint-imports` clean.
  - Unit tests: 488 passed.
  - Integration on a clean database: 26 passed, 1 skipped, 2 deselected.
