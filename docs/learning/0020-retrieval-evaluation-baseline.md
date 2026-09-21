# 0020 Evidence Retrieval Evaluation Baseline

## What Changed

The repository now has a versioned synthetic development set and an offline
evaluator for the existing lexical and exact-skill Top-5 retriever. The evaluator
saves every ranked candidate plus macro Recall@1/3/5, MRR@5, and a separate
negative-query accuracy measure.

Production Analysis Runs still use exactly the same retriever. No real embedding
provider, pgvector query, or evidence matcher was added.

## Why It Exists

Without a frozen dataset and metric definition, a later vector or hybrid retriever
could look better because the examples or scoring rules changed. Measuring the
simple baseline first creates a fair comparison point and reveals which failures
semantic retrieval should address.

## Failure Modes It Prevents

- Comparing retrieval implementations on different examples.
- Reporting a hit while ignoring other relevant Experiences that were missed.
- Silently assigning meaningless Recall or MRR values to gap queries.
- Losing the exact ranking behind an aggregate score.
- Replacing prior evidence by rerunning into the same output file.
- Treating deterministic fake vectors as semantic retrieval evidence.

## How To Verify It

Run the focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests/test_evidence_retrieval.py `
  tests/test_evidence_retrieval_evaluation.py
```

Generate a new report using a new output filename:

```powershell
.\.venv\Scripts\python -m careerops.evaluation.run_evidence_retrieval `
  --dataset evals/evidence_retrieval_v1.json `
  --output docs/metrics/YYYY-MM-DD-lexical-retrieval-baseline.json `
  --git-revision <commit-or-working-tree-label>
```

The command is offline and does not inspect provider configuration or make a model
request.

## What You Must Understand

Level 1:

- Recall@K measures how much of all relevant evidence entered the candidate set;
  it is not the same as whether any one result matched.
- MRR emphasizes the rank of the first relevant result and ignores additional
  relevant results after that first hit.
- Queries with no relevant evidence need a separate rejection metric because
  Recall and MRR have no relevant denominator.
- Development-set scores can guide engineering but do not establish production
  accuracy or independent generalization.
- The fake embedding provider verifies lifecycle behavior only; it cannot support a
  semantic retrieval-quality claim.

Level 2:

- The evaluator converts labeled Pydantic records into the same domain records used
  by the production retriever.
- Stable UUID labels and a saved dataset hash make a report traceable.
- Per-query rankings make aggregate metrics auditable.
- Refusing to overwrite output preserves comparisons across retriever versions.

## Knowledge Check

1. Why can Hit@5 be perfect while Recall@5 is below one?
2. Why is MRR insufficient when several Experiences are relevant?
3. Why are zero-relevance queries excluded from Recall and MRR?
4. What does the separate negative-query metric consider a successful result?
5. Why can the current fake vectors not be used to evaluate semantic retrieval?
6. What must remain fixed when comparing lexical, vector, and hybrid retrievers?
