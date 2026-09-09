# 0014 Requirement Parser Evaluation

## What Changed

The repository now contains a 12-case labeled development set, a deterministic
scorer, a live evaluation command, raw v1/v2 reports, and an evidence-backed
prompt revision from copied quotes to candidate-ID grounding.

## Why It Exists

Unit tests prove code behavior with controlled inputs. They cannot measure a
changing model's extraction quality. An evaluation dataset makes expected
behavior explicit and preserves failures instead of relying on a few successful
demos.

## Failure Modes It Prevents

- Claiming quality from one or two successful examples.
- Mixing extraction, category, and skill errors into one unexplained score.
- Silently excluding provider or grounding failures.
- Editing labels to match model output without review.
- Overwriting an earlier result after changing the prompt.
- Treating a tuned development-set score as holdout performance.

## How To Verify It

Run scorer unit tests without network access:

```powershell
.\.venv\Scripts\python -m pytest tests/test_requirement_parser_evaluation.py
```

Run a new live report only with a new output filename:

```powershell
.\.venv\Scripts\python -m careerops.evaluation.run_requirement_parser `
  --dataset evals/job_requirements_v1.json `
  --output docs/metrics/YYYY-MM-DD-groq-requirement-eval.json `
  --git-revision <commit-or-working-tree-label>
```

The command refuses to overwrite existing evidence.

## What You Must Understand

Level 1: Extraction precision answers how many predicted source texts were
expected. Recall answers how many expected source texts were found. F1 balances
the two.

Level 1: Category and skill accuracy use only text-matched requirements. This
prevents an extraction miss from being counted again as a classification miss.

Level 1: v2 improved on the same cases used to diagnose v1, so it is development
evidence, not an unbiased holdout result.

Level 2: Candidate-ID grounding moves exact text preservation into deterministic
code. The LLM still decides which candidate is a requirement and how to classify
it, so semantic validation remains necessary.

## Knowledge Check

1. What different questions do extraction precision and recall answer?
2. Why is category accuracy calculated only on text matches?
3. Why must v1 evidence remain after v2 improves it?
4. Why can the v2 result not be called production accuracy?
5. What makes a future holdout set different from this development set?
