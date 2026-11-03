# 0057 Parser Heading Filter (parse-v4)

## What Changed

- The parser no longer shows the model lines that are section headings (ADR-050).
  Those are lines that, after removing HTML tags:
  - end with a colon;
  - are known section titles;
  - are short all-caps titles;
  - are HTML headings; or
  - are empty markup.
- Candidate IDs and character spans are unchanged.
- `PARSE_PROMPT_VERSION` is `parse-v4`.

## Why It Exists

The prompt already told the model to ignore headings, but in large_scale_v1 it
still stored 71 headings among 1,804 analysed requirements. The matcher then
sometimes marked a heading like "Requirements:" as "matched", with an unrelated
quote. That is a positive claim about nothing. A rule in code is enforced every
time; a rule in a prompt is only a request.

## Failure Modes It Prevents

- Over-claims on text that is not a requirement.
- Wasted output tokens and noisier categories in parser calls.
- Inflated requirement counts, which push large jobs into more matcher batches
  and more truncation.

## How It Was Verified

- **Unit tests.** Heading and non-heading lines, ID and span preservation, and
  the only-headings case.
- **Label check.** Against 5,164 adjudicated parser labels, the rule removes one
  real requirement, a lead-in line.
- **Real-provider check.** Same 150 pairs, replayed parses without headings.
  Over-claiming went from 39/1,098 to 24/1,022 overall. On the same 259
  requirements of 50 common pairs, over-claims were 5, 8 and 3 for the original,
  batch-6 and batch-6-with-filter runs.

## What The Author Must Understand

- **Rules in code versus the prompt.** Use code for rules that are cheap to
  state exactly. Use the prompt only for judgment calls.
- **Why IDs are preserved.** Labels, grounding and spans all refer to candidate
  IDs from `extract_source_candidates`. Renumbering would silently break every
  evaluation and the span checks.
- **Why the version changed.** The prompt text is the same, but the model sees
  different input, so old and new parses must be distinguishable.
- **How the check was run.** The real-provider check replayed parses with
  headings removed instead of running a real `parse-v4` parse. It measures the
  filter's effect on matching, not on the parser's own selection.

## Knowledge Check

1. Why does the filter run before the model call and not on the model's output?
2. Which rule would drop "Responsibilities:" and which would drop
   "FRONTEND PROGRAMMER INTERN"? Why is "SQL" kept?
3. What would break if filtered candidates were renumbered from 0?
4. The label check found one real requirement removed. What was it, and why is
   the loss acceptable?
5. Why was the matcher's over-claim comparison scored only on requirements both
   runs analysed?
