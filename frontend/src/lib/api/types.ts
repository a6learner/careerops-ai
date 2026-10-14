export const EXPERIENCE_KINDS = ["project", "work", "research", "course", "other"] as const;
export type ExperienceKind = (typeof EXPERIENCE_KINDS)[number];

export type Experience = {
  id: string;
  title: string;
  kind: ExperienceKind;
  description: string;
  skills: string[];
  outcome: string | null;
  version: number;
  content_hash: string;
  created_at: string;
  updated_at: string;
};

export type ExperienceList = { items: Experience[] };

export const JOB_STATUSES = [
  "saved",
  "preparing",
  "applied",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

export type Job = {
  id: string;
  company: string;
  title: string;
  raw_description: string;
  description_hash: string;
  source_url: string | null;
  location: string | null;
  deadline: string | null;
  status: JobStatus;
  version: number;
  created_at: string;
  updated_at: string;
};

export type JobList = { items: Job[]; next_cursor: string | null };

export type ParseRunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type RequirementCategory =
  | "must_have"
  | "nice_to_have"
  | "responsibility"
  | "education";

export type JobRequirement = {
  id: string;
  category: RequirementCategory;
  text: string;
  skill_normalized: string | null;
  source_span_start: number | null;
  source_span_end: number | null;
};

export type ParseRun = {
  id: string;
  job_id: string;
  status: ParseRunStatus;
  idempotency_key: string;
  input_fingerprint: string;
  model_name: string;
  prompt_version: string;
  attempt: number;
  error_code: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  requirements: JobRequirement[];
};

export type EvidenceVerdict = "matched" | "partial" | "missing" | "insufficient_evidence";
export type EvidenceMatch = {
  id: string;
  requirement_id: string;
  experience_id: string | null;
  experience_version: number | null;
  verdict: EvidenceVerdict;
  quote: string | null;
  quote_valid: boolean;
  confidence: number | null;
};

export type AnalysisRun = {
  id: string;
  job_id: string;
  parse_run_id: string;
  status: ParseRunStatus;
  idempotency_key: string;
  input_fingerprint: string;
  model_name: string;
  prompt_version: string;
  attempt: number;
  validation_failure_count: number;
  error_code: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  matches: EvidenceMatch[];
};

export const ACTION_ITEM_STATUSES = ["todo", "doing", "done"] as const;
export type ActionItemStatus = (typeof ACTION_ITEM_STATUSES)[number];
export type ActionItem = {
  id: string;
  job_id: string;
  source_evidence_match_id: string | null;
  title: string;
  status: ActionItemStatus;
  version: number;
  job_is_archived: boolean;
  created_at: string;
  updated_at: string;
};
export type ActionItemList = { items: ActionItem[]; next_cursor: string | null };

export type DashboardSummary = {
  generated_at: string;
  jobs: Record<JobStatus | "total", number>;
  action_items: Record<ActionItemStatus | "total", number>;
};

export type AssistedRunStatus = "queued" | "running" | "succeeded" | "failed";
export type DraftStatus = "pending" | "confirmed" | "rejected";

export type SourceReference = {
  field: string;
  start: number;
  end: number;
  quote: string;
};

export type ExperienceDraft = {
  id: string;
  cv_import_id: string;
  status: DraftStatus;
  title: string;
  kind: ExperienceKind;
  description: string;
  skills: string[];
  outcome: string | null;
  source_refs: SourceReference[];
  version: number;
  confirmed_experience_id: string | null;
  created_at: string;
  updated_at: string;
};

export type CvImport = {
  id: string;
  status: AssistedRunStatus;
  filename: string;
  document_type: "pdf" | "docx" | "doc" | "odt" | "rtf" | "txt" | "markdown";
  media_type: string;
  size_bytes: number;
  content_sha256: string;
  extractor_name: string;
  attempt: number;
  error_code: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  drafts: ExperienceDraft[];
};

export type JobDiscoveryResult = {
  id: string;
  provider_result_id: string;
  company: string;
  title: string;
  source_url: string;
  summary: string;
  raw_description: string | null;
  location: string | null;
  published_at: string | null;
  observed_at: string;
};

export type JobDiscoveryRun = {
  id: string;
  status: AssistedRunStatus;
  query: string;
  location: string | null;
  remote: boolean | null;
  published_within_days: number | null;
  query_fingerprint: string;
  provider_name: string;
  attempt: number;
  error_code: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  results: JobDiscoveryResult[];
};

export type JobDraft = {
  id: string;
  result_id: string;
  status: DraftStatus;
  company: string;
  title: string;
  raw_description: string | null;
  source_url: string;
  location: string | null;
  version: number;
  confirmed_job_id: string | null;
  created_at: string;
  updated_at: string;
};
