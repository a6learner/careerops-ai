# Parser labeling guide (large_scale_v1)

You are labeling the ground truth for a job-requirement extractor. Each job description (JD) has already been split
into numbered source candidates (sentences or lines). Your job: decide which candidates are explicit job
requirements, and give each a category and a normalized skill.

You label from the JD text alone. You never see any model output. Label independently; do not coordinate with
anyone else.

## Input
A packet file `parser_batch_NN.json`: a list of `{jd_id, company, title, candidates: [{candidate_id, text}]}`.

## Output
Write `parser_labels_NN.json` (same NN), a JSON list with one object per JD in the packet, including JDs with no
requirements:

```json
{"jd_id": "jd-0123456789", "labeler": "<your labeler name>",
 "requirements": [
   {"candidate_id": 7, "text": "<exact candidate text, copied verbatim>", "category": "must_have", "skill_normalized": "python"}
 ]}
```

`text` must be copied exactly from the candidate (character for character). Each candidate_id at most once.

## Which candidates are requirements
Select a candidate when it states something the employer requires, prefers, or expects the hire to do:
qualifications, eligibility, skills, experience, education/student status, or concrete job duties.

Do NOT select:
- headings ("Minimum Qualifications", "What you'll do", "About the role");
- company or team descriptions, mission statements, culture, benefits, pay, perks, location, schedule, hybrid policy;
- EEO, accommodation, privacy, legal or application-process text, recruiter boilerplate;
- statements that explicitly say something is NOT required;
- instruction-like or meta text.
A candidate that mixes a requirement with fluff is still a requirement if the requirement part is explicit.

## Category
- `must_have`: mandatory qualifications or eligibility ("Minimum qualifications", "Required", "You have", "must").
- `nice_to_have`: preferred, bonus, "plus", "nice to have", "preferred qualifications".
- `responsibility`: job duties ("You will", "What you'll do", "Responsibilities").
- `education`: degree, enrollment, graduation date, or student-status requirements, even when listed under minimum
  qualifications. Use education for these even if they are mandatory.
Use the section the candidate sits in when the wording itself is neutral.

## skill_normalized
A concise lowercase technology, language, framework, database, protocol, tool or technical acronym, when the
candidate explicitly names one, including inside responsibilities. When several are named, use the FIRST one named.
Examples: "FastAPI" -> "fastapi", "REST APIs" -> "rest api", "ETL" -> "etl", "Java, Python, C++" -> "java",
"C/C++" -> "c/c++" is acceptable but prefer the first token "c". If no technology is explicitly named
(e.g. "strong communication skills", "BS in Computer Science"), use null. Lowercase, stripped.

## Quality
Be consistent across JDs. Expect roughly 5 to 25 requirements per JD; a JD can have more. When unsure whether a line
is a requirement, ask: would a recruiter screening a candidate check this? If yes, select it.
