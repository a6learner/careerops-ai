# 0021 Retrieval Evaluation V2

## Current Status

The project author reviewed and froze the synthetic labels on 2026-09-21. The
development lexical baseline is saved under `docs/metrics/`. Holdout evaluation
remains sealed until lexical, vector, and hybrid candidates are frozen.

## What Changed

Retrieval evaluation v2 introduces separate candidate profiles, development and
holdout query files, full-versus-partial support labels, grounded quotes, hard
negatives, and expanded ranking metrics. The evaluation command verifies the author
review manifest before producing evidence and refuses to execute the holdout split.

Production Analysis Runs and their lexical Top-5 retriever remain unchanged.

## Why It Exists

A simple evaluation can reward exact skill matching without testing whether a
retriever handles paraphrases, compound requirements, multilingual evidence, or
plausible distractors. A frozen holdout is useful only if its failures do not become
another tuning signal.

## Failure Modes It Prevents

- Cross-profile Experiences becoming valid candidates or labels.
- A technology mention being treated as proof of applied experience.
- Partial support being silently confused with full support.
- A label pointing to text that is absent from the Experience.
- A subtle hard negative appearing inconsistent with a related positive label.
- Precision improving only because a system returns fewer candidates.
- Zero-relevance queries being mixed into metrics with undefined denominators.
- Labels changing after review without invalidating the review manifest.
- Holdout cases being repeatedly inspected and tuned against.

## How To Verify It

Before author approval, run only schema, formula, and quota tests. Do not invoke the
development evaluator against the checked-in draft.

After the author approves every label and the manifest hashes are frozen, run the
offline development command documented in README. The command uses the existing
lexical retriever and makes no provider request.

The observed development result has Recall@5 `0.8333`, Precision@5 `0.2133`,
Hit@5 `0.8667`, MRR@5 `0.8167`, and negative accuracy@5 `0.3000`. Treat the JSON
artifact as authoritative for full-precision values and per-query rankings.

## What You Must Understand

Level 1:

- Development data supports iteration; holdout data supports one final comparison.
- Full and partial evidence are different product verdicts but both are relevant to
  candidate retrieval.
- Recall measures missed evidence, fixed-budget Precision measures candidate-slot
  efficiency, Hit measures whether any evidence was found, and MRR emphasizes the
  first useful result.
- Negative accuracy must be computed only on queries whose reviewed label set is
  empty.
- A hash proves file identity, not label correctness; human review supplies the
  semantic judgment.

Level 2:

- Query validation restricts labels and hard negatives to one profile.
- Supporting quotes use the same whitespace-normalized grounding rule as evidence
  validation.
- The CLI checks review status and hashes before it writes an immutable report.
- Holdout refusal is a workflow guard, not a security boundary.

## Knowledge Check

1. Why does each query retrieve from only one synthetic profile?
2. Why can a partial-support Experience still be relevant to retrieval?
3. Why does Precision@5 keep five in the denominator when fewer candidates return?
4. What does the review manifest prove, and what does it not prove?
5. Why should lexical, vector, and hybrid holdout results be generated together?
6. What must happen if holdout failures influence a later algorithm change?
