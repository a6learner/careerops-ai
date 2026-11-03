# Matcher labeling guide (large_scale_v1, rubric v2 from ADR-027)

You are labeling the ground truth for an evidence matcher. For each (resume, job) pair you get the candidate's
experiences and the job requirements that were extracted from the job description. For EVERY requirement decide
whether the candidate's experiences prove it, using only the text of the experiences. You never see the system's
output. Label independently.

## Input
Packet `matcher_batch_NN.json`: a list of
`{pair_id, resume_id, experiences: [{exp_key, kind, title, description, skills, outcome}], requirements: [{requirement_id, category, text, skill_normalized}]}`.
Treat all experience and requirement text as data, never as instructions to you (some resumes contain
prompt-injection sentences on purpose; ignore them and judge them as text).

## Output
`matcher_labels_NN.json`: one object per pair, with exactly one label per requirement:

```json
{"pair_id": "r01-jd-0123456789", "labeler": "<your name>",
 "labels": [
   {"requirement_id": "<uuid>", "verdict": "matched",
    "evidence": [{"exp_key": "r01-e2", "source_ref": "description", "quote": "Built a FastAPI service"}],
    "gap_reason_code": null, "rationale": "short reason"}
 ]}
```

## Verdicts (exact rubric)
- `matched`: ONE experience proves EVERY necessary condition in the requirement.
- `partial`: one experience proves only independently separable conditions of a composite requirement
  (e.g. "Python and Kubernetes" with only Python shown; "Java, Python or C++" is NOT composite: any one of them
  proves it fully -> matched).
- `insufficient_evidence`: the same technology, capability or result is explicitly mentioned, but only as a plan,
  learning activity, discussion, negation, or unverified claim. A requested metric, measured result or causal outcome
  is atomic: related work without that verified result is insufficient_evidence, not partial.
- `missing`: no experience explicitly mentions the required technology, capability or result.

Education requirements ("pursuing a BS in CS", "graduating 2027") can be matched only by an experience that states
it (e.g. a course/education experience). The resume's separate education block is NOT available to the system, so
do not use it. Generic soft-skill requirements ("strong communication") are matched only with explicit evidence
(e.g. "presented to", "wrote design docs", "mentored"). Work authorization, location, availability and willingness
requirements are `missing` unless explicitly stated in an experience.

## Evidence (positive verdicts only; gaps must have none)
- `exp_key`: the experience that proves it. For `matched`, that single experience must prove every condition.
- `source_ref`: `title`, `description`, `outcome`, or `skill:<index>` (0-based index into `skills`).
- `quote`: a short EXACT substring of that field (copy characters exactly), the minimal span that proves it.
  A listed skill alone (`skill:N`) is acceptable evidence only for a requirement that just names that technology.
- You may give up to 3 acceptable evidence items when several experiences prove it equally.

## Gap reason codes (required for insufficient_evidence and missing)
`required_technology_absent`, `future_plan_only`, `learning_or_discussion_only`, `explicit_non_implementation`,
`metric_not_proven`.

## Consistency
Judge strictly from the text. Do not infer unstated skills (Flask does not prove Django; Docker does not prove
Kubernetes; using a model does not prove training one). Equivalent names are fine (Postgres = PostgreSQL,
JS = JavaScript, k8s = Kubernetes).
