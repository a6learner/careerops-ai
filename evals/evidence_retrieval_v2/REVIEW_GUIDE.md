# Retrieval Evaluation V2 Label Review Guide

## Status

The corpus and query files are synthetic drafts. Structural validation has passed,
but the project author has not approved the semantic labels. Do not generate a
development or holdout score while `review_manifest.json` remains
`pending_author_review`.

## Review Unit

Review the four Experience profiles first. Then review queries in batches of ten.
For each query, inspect the requirement against every labeled relevant Experience
and every explicit hard negative in the same profile.

Respond to each row with one of:

```text
approve
change full to partial
change partial to full
remove relevant <experience_id>
add relevant <experience_id> as full|partial with quote "..."
replace hard negative <old_id> with <new_id>
make this a negative query because ...
```

## Relevance Rules

`full` means the supporting quote itself grounds all substantive clauses of the
requirement. Do not depend on an unquoted field to complete the claim. If one
Experience contains the needed facts in separate fields but no concise grounded
quote supports the full requirement, rewrite the synthetic Experience before
freezing or label only the supported part as `partial`.

`partial` means the quote grounds at least one substantive clause but not the whole
requirement. Multiple partial Experiences may all be relevant because candidate
retrieval should expose each valid source even though the current matcher persists
at most one citation per requirement.

For `A or B`, an Experience that satisfies one complete branch may be `full` when it
also satisfies every clause shared by both branches. For `A and B`, satisfying only
one side is `partial`.

A skill name alone is evidence only for a requirement that asks for familiarity
with that skill. Requirements about building, operating, measuring, or achieving an
outcome need a quote showing that activity. Reading, presenting, considering a
future rewrite, or using a neighboring technology is not positive evidence.

## Negative And Hard-Negative Rules

A zero-relevance query must have no Experience in its profile that could support
even a `partial` verdict. Its negative rationale must explain why the closest
candidate is insufficient.

A hard negative should be plausibly confusable because of shared vocabulary,
technology family, domain, or task shape, while still lacking valid support. A
random unrelated Experience is not a useful hard negative.

When the relevance boundary is easy to misread, `hard_negative_rationale` records
why the distractor remains invalid despite the similarity. It explains the label;
it cannot compensate for a distractor that actually provides partial support.

## Split Discipline

Development labels may be used for retrieval design after author approval. Holdout
labels are reviewed and frozen at the same time, but no holdout ranking or metric is
generated until lexical, vector, and hybrid candidates are all frozen.

After approval, update the manifest with `approved_frozen`, `project author`, the
review timestamp, and hashes of all three JSON files. Any later data edit invalidates
the manifest and requires another review. If holdout results influence a retrieval
change, create a new holdout rather than rerunning against the old one.
