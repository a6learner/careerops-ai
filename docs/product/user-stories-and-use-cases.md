# CareerOps AI User Stories And Use Cases

## Product Vision

CareerOps AI helps students and early-career candidates align their real
experiences with target job descriptions, identify which evidence to emphasize
for resumes and interviews, and turn missing evidence into concrete preparation
actions.

The long-term product can serve candidates across majors and role families. The
MVP starts with internship-style job preparation because it gives the backend a
clear, testable workflow: user-owned data, job descriptions, asynchronous
analysis, evidence validation, action items, and application status tracking.

## MVP Product Goal

The MVP helps one candidate complete this loop:

```text
register/login -> build experience library -> save job description
-> parse structured requirements -> match requirements to real evidence
-> review evidence and gaps -> create action items -> track application status
```

The most important user outcome is not a generic score. The user should know:

- which real experiences are most relevant to a specific job description
- what to emphasize in resume tailoring or interview preparation
- which requirements are weak, missing, or unsupported by evidence
- which gaps should become concrete preparation tasks

The engineering goal remains backend reliability. The product goal gives that
engineering work a user-facing reason.

## Primary Users

### Student Or Early-Career Candidate

This user may be a CS student, another major applying to role-aligned
internships, a career switcher, or an early-career candidate preparing for
full-time applications.

They may have experiences from:

- course projects
- personal projects
- internships or work
- research
- club or student organization work
- volunteering
- competitions or hackathons
- leadership, teaching, mentoring, or community activity
- personal interests that are relevant to a role

For the current implementation, structured experience kinds remain:

```text
project | work | research | course | other
```

Broader experiences such as club activity, volunteering, leadership, and hobbies
fit under `other` for now. This avoids an early database/API contract change
while keeping the product language broad enough for non-CS candidates.

### Candidate With Few Experiences

Some users may not yet have strong projects or role-specific evidence. For them,
the product should still be useful after they paste a target JD:

- show which requirements currently lack evidence
- help turn gaps into action items
- later suggest project or preparation ideas grounded in repeated JD patterns

The MVP should stop at gap-to-action-item. Rich project recommendation can be a
future feature after the evidence matching loop is reliable.

## Product Principles

### Evidence Before Claims

The system must not claim the user has a skill, outcome, or experience unless it
can point to user-owned evidence.

If evidence is missing, the product should say that clearly. Missing evidence is
not a failure of the user; it is useful information for planning.

### Suggestions, Not Fabrication

The product may help the user understand what to emphasize. It should not invent
experience, inflate impact, or generate unsupported resume bullets.

### JD-Driven Preparation

The product starts from a concrete target job description. Different jobs may
emphasize different parts of the same candidate's experience library.

### Backend Reliability Supports Product Trust

Authorization, versioning, idempotency, async runs, and database constraints are
not just technical decorations. They protect user data and prevent misleading
career advice.

## Core User Stories

### US-001: Build An Experience Library

As a student or early-career candidate, I want to save my real experiences with
context, skills, and outcomes so that future job analysis can cite evidence
instead of guessing.

Development alignment:

- `experiences` table
- Experiences CRUD
- object-level authorization
- soft deletion
- content hashing
- future embedding generation

### US-002: Keep My Career Data Private

As a candidate, I want only my account to access my experiences, jobs, analyses,
and action items so that other users cannot see or change my private career
data.

Development alignment:

- authentication
- current-user dependency
- repository queries filtered by `user_id`
- cross-user authorization tests returning 404

### US-003: Save A Target Job Description

As a candidate, I want to save a specific job description with company, title,
status, source, and deadline so that I can prepare for that role over time.

Development alignment:

- Jobs CRUD
- application status lifecycle
- cursor pagination
- object-level authorization
- soft deletion

Implementation status: first backend slice complete.

### US-004: Extract Job Requirements

As a candidate, I want the system to parse a raw job description into structured
requirements so that I can see what the role is actually asking for.

Development alignment:

- parse run resource
- asynchronous worker
- idempotent submission
- prompt/model version tracking
- source span validation
- retry and failure states

### US-005: Match Requirements To Evidence

As a candidate, I want each job requirement matched to my real experiences so
that I know what to emphasize in my resume or interviews.

Development alignment:

- analysis run resource
- retrieval over experience embeddings
- LLM adapter boundary
- schema validation
- citation validation
- database constraints for evidence matches
- immutable historical analysis results

### US-006: Identify Gaps

As a candidate, I want unsupported requirements to be shown as gaps so that I do
not mistake weak evidence for real readiness.

Development alignment:

- explicit verdicts such as `missing` and `insufficient_evidence`
- quote validation
- no single match percentage score
- evidence-first UI states

### US-007: Turn Gaps Into Action Items

As a candidate, I want to convert gaps into preparation tasks so that I can take
specific steps before applying or interviewing.

Development alignment:

- action items CRUD
- links from action items to jobs, requirements, or analysis results
- dashboard summary
- cache invalidation when task state changes

### US-008: Track Application Progress

As a candidate, I want to track each job's status so that I can manage my
application pipeline and preparation work in one place.

Development alignment:

- job status enum
- dashboard aggregates
- cache invalidation on job updates
- status-filtered list queries

### US-009: Prepare Resume Tailoring Inputs

As a candidate, I want evidence-grounded suggestions or prompts for another AI
tool so that I can tailor my resume without inventing unsupported claims.

Development alignment:

- future resume-tailoring prompt export
- citations back to experiences
- explicit instruction to avoid unsupported claims
- not part of the current MVP implementation

## Core Use Cases

### UC-001: Create An Experience

Trigger: The user wants to add a project, work experience, course, research
work, or other relevant background.

Preconditions:

- The user is registered and logged in.

Main flow:

1. The user submits title, kind, description, skills, and optional outcome.
2. The API authenticates the request.
3. The service computes a deterministic `content_hash`.
4. The repository writes the experience with the current user's `user_id`.
5. The API returns the created experience with version `1`.

Failure and edge cases:

- Missing or invalid token returns 401.
- Blank required fields return 422.
- Another user cannot create an experience for someone else's `user_id`.

Backend implications:

- The API must not trust a client-supplied owner id.
- The owner comes from the current-user dependency.
- The database stores enough metadata for future embedding invalidation.

### UC-002: Update An Experience Without Losing Another Edit

Trigger: The user edits an existing experience.

Preconditions:

- The user owns the experience.
- The client has the latest known `version`.

Main flow:

1. The client sends `PATCH /api/v1/experiences/{id}` with `If-Match`.
2. The service compares `If-Match` to the current stored version.
3. If the version matches, the update is applied.
4. The version increments.
5. The content hash is recomputed.
6. The embedding is cleared so a future worker can regenerate it.

Failure and edge cases:

- Missing or malformed `If-Match` returns 428.
- Stale version returns 409.
- Cross-user access returns 404.
- Soft-deleted experiences behave as not found.

Backend implications:

- Optimistic locking prevents lost updates.
- Meaningful content changes invalidate derived data.

### UC-003: Save A Job Description

Trigger: The user finds a target job and wants to prepare for it.

Preconditions:

- The user is logged in.

Main flow:

1. The user submits company, title, raw description, and optional metadata.
2. The API stores the job under the current user's account.
3. The system computes `description_hash`.
4. The job appears in the user's job list.

Failure and edge cases:

- Blank description returns 422.
- Invalid status transitions return a domain error.
- Cross-user access returns 404.

Backend implications:

- Jobs need object-level authorization like experiences.
- Lists need pagination and indexes because job data grows over time.

### UC-004: Parse Requirements From A Job

Trigger: The user asks the system to analyze a saved job description.

Preconditions:

- The job exists and belongs to the current user.
- The job has a raw description.

Main flow:

1. The user submits a parse request.
2. The API creates or reuses a parse run using an idempotency key.
3. The API returns 202 with the run id.
4. A worker parses requirements asynchronously.
5. Parsed requirements are stored with source spans.
6. The user can poll the run resource for status and results.

Failure and edge cases:

- Repeated clicks with the same idempotency key do not create duplicate runs.
- Invalid LLM output is retried or marked failed with a structured error.
- API request latency does not depend on model latency.

Backend implications:

- API service must not call the LLM directly.
- Runs are resources with status, not hidden function calls.

### UC-005: Analyze Evidence For A Job

Trigger: The user wants to know which experiences support a job's requirements.

Preconditions:

- The job belongs to the current user.
- Parsed requirements exist.
- The user has at least one active experience.

Main flow:

1. The user submits an analysis request.
2. The API creates or reuses an analysis run.
3. A worker retrieves candidate experiences.
4. The LLM proposes requirement-to-evidence matches.
5. The system validates schema, ownership, versions, and quotes.
6. Validated matches and gaps are written atomically.
7. The user reviews evidence and gaps.

Failure and edge cases:

- Unsupported claims are downgraded to insufficient evidence.
- Direct database writes cannot persist a positive match without evidence.
- Worker crashes do not leave the run permanently stuck.

Backend implications:

- Evidence validation is the technical center of the project.
- Database constraints backstop application validation.
- Analysis results should be immutable once succeeded.

### UC-006: Convert A Gap Into An Action Item

Trigger: The user sees a missing or weak requirement and wants to prepare.

Preconditions:

- The user owns the analysis result.
- The gap is tied to a requirement or evidence match.

Main flow:

1. The user selects a gap.
2. The system creates an action item linked to the job or requirement.
3. The user tracks status such as todo, doing, or done.
4. Dashboard aggregates update.

Failure and edge cases:

- Cross-user references return 404.
- Deleting a job does not break existing task display.
- Dashboard cache must be invalidated after task changes.

Backend implications:

- Action items need ownership and reference integrity.
- Cache is useful only if invalidation is correct.

## MVP User Flow

```text
1. Register or log in
2. Add experiences
3. Save a target job description
4. Submit parse run
5. Review structured requirements
6. Submit analysis run
7. Review matched evidence and gaps
8. Convert selected gaps into action items
9. Update job and task status
10. View dashboard summary
```

This flow is the product's spine. Features that do not support this flow are not
P0.

## Development Alignment

| Module | User Value | Engineering Concept |
|---|---|---|
| Auth | Keep private career data private | authentication, password hashing, JWT |
| Current user | Identify request owner | dependency injection, source-of-truth lookup |
| Experiences | Build evidence library | CRUD, ownership, soft deletion, optimistic locking |
| Jobs | Save target roles | resource modeling, status, pagination |
| Parse runs | Understand JD requirements | async submission, idempotency, LLM boundary |
| Analysis runs | Match JD to real evidence | retrieval, validation, transactions |
| Evidence matches | Prevent unsupported claims | schema checks, quote checks, DB constraints |
| Action items | Turn gaps into work | state tracking, references, authorization |
| Dashboard | See preparation progress | aggregation, caching, invalidation |

## Future Scope

These are useful, but not required for the MVP:

- Generate an evidence-grounded prompt for another AI resume editor.
- Upload an existing resume and compare it against a JD.
- Batch tailor suggestions across multiple JDs.
- Recommend projects or preparation plans based on repeated JD patterns.
- Support richer experience kinds such as volunteer, activity, leadership, or
  personal interest as first-class enum values.
- Import experiences from GitHub, documents, or other sources.

Future resume-related features must preserve the evidence rule: generated
suggestions may reframe real experience, but must not invent claims.

## MVP Non-Goals

The MVP does not:

- directly generate complete resumes
- automatically submit applications
- scrape job boards at scale
- promise employment outcomes
- produce a single match percentage score
- invent projects, skills, metrics, or work history
- support team or recruiter workflows

## Product Success Criteria

The MVP is useful when a candidate can:

- create a personal experience library
- save a real job description
- see structured requirements
- see which requirements have evidence
- see which requirements are gaps
- create action items from selected gaps
- track job status through the application process

The MVP is engineering-ready when these behaviors are protected by tests for
authorization, validation, idempotency, concurrency, database constraints, and
failure handling as each module is implemented.
