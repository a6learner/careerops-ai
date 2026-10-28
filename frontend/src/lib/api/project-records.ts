export type ProjectRecord = { id: string; name: string; goal: string; created_at: string };
export type RecordStatus = "draft" | "confirmed" | "withdrawn";
export type EvidenceSource = {
  kind: "repository_excerpt" | "test_output" | "user_note";
  locator: string;
  content: string;
  quote: string;
};
export type CheckpointPayload = {
  title: string;
  objective: string;
  changes: string;
  decisions: string;
  failures: string;
  verification: string;
  remaining: string;
  contribution: string;
  host: string;
  base_revision: string | null;
  sources: EvidenceSource[];
};
export type CheckpointRecord = {
  id: string;
  project_id: string;
  status: RecordStatus;
  version: number;
  payload: CheckpointPayload;
  content_sha256: string;
  contribution_note: string;
  created_at: string;
  reviewed_at: string | null;
};
export type RecordPage<T> = { items: T[]; next_cursor: string | null };
