import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { AnalysisRunPanel } from "@/components/jobs/analysis-run-panel";
import type { AnalysisRun, Job, ParseRun } from "@/lib/api/types";

const job: Job = {
  id: "job-id", company: "Example", title: "Backend Intern", raw_description: "Python required.",
  description_hash: "hash", source_url: null, location: null, deadline: null, status: "saved",
  version: 1, created_at: "2026-10-10T00:00:00Z", updated_at: "2026-10-10T00:00:00Z",
};
const parseRun: ParseRun = {
  id: "parse-id", job_id: job.id, status: "succeeded", idempotency_key: "parse-key",
  input_fingerprint: "fingerprint", model_name: "local-fake-parser", prompt_version: "parse-v2",
  attempt: 1, error_code: null, latency_ms: 1, input_tokens: null, output_tokens: null,
  started_at: null, finished_at: "2026-10-10T00:00:00Z", created_at: "2026-10-10T00:00:00Z",
  requirements: [
    { id: "req-1", category: "must_have", text: "Python required.", skill_normalized: "python", source_span_start: 0, source_span_end: 16 },
    { id: "req-2", category: "nice_to_have", text: "Redis preferred.", skill_normalized: "redis", source_span_start: 17, source_span_end: 33 },
  ],
};
const succeeded: AnalysisRun = {
  id: "analysis-id", job_id: job.id, parse_run_id: parseRun.id, status: "succeeded",
  idempotency_key: "analysis-key", input_fingerprint: "fingerprint", model_name: "fake-matcher",
  prompt_version: "v1", attempt: 1, validation_failure_count: 0, error_code: null,
  latency_ms: 2, input_tokens: null, output_tokens: null, started_at: null,
  finished_at: "2026-10-10T00:00:00Z", created_at: "2026-10-10T00:00:00Z",
  matches: [
    { id: "match-1", requirement_id: "req-1", experience_id: "exp-1", experience_version: 2, verdict: "matched", quote: "Built Python APIs", quote_valid: true, confidence: 0.9 },
    { id: "match-2", requirement_id: "req-2", experience_id: null, experience_version: null, verdict: "missing", quote: null, quote_valid: false, confidence: 0.8 },
  ],
};

describe("AnalysisRunPanel", () => {
  it("shows validated evidence and creates an action item from a gap", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/experiences")) return Response.json({ items: [{ id: "exp-1", title: "API Project", kind: "project", description: "Built Python APIs", skills: ["Python"], outcome: null, version: 2, content_hash: "hash", created_at: "", updated_at: "" }] });
      if (url.endsWith("/api/v1/action-items")) return Response.json({ id: "item-id" }, { status: 201 });
      if (init?.method === "POST") return Response.json(succeeded, { status: 202 });
      return Response.json(succeeded);
    });
    const user = userEvent.setup();
    renderWithQuery(<AnalysisRunPanel job={job} parseRun={parseRun} />);

    await user.click(screen.getByRole("button", { name: "Analyze evidence" }));
    expect(await screen.findByText(/Built Python APIs/)).toBeInTheDocument();
    expect(screen.getByText(/No validated positive evidence/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create action item" }));

    await screen.findByText("Action item created.");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/api/v1/action-items",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ job_id: "job-id", title: "Address gap: Redis preferred.", source_evidence_match_id: "match-2" }),
      }),
    );
  });

  it("shows a durable analysis failure without evidence claims", async () => {
    const failed = { ...succeeded, status: "failed", error_code: "MATCHER_OUTPUT_INVALID_SCHEMA", matches: [] } satisfies AnalysisRun;
    vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json(failed, { status: 202 }));
    const user = userEvent.setup();
    renderWithQuery(<AnalysisRunPanel job={job} parseRun={parseRun} />);

    await user.click(screen.getByRole("button", { name: "Analyze evidence" }));

    expect(await screen.findByText(/MATCHER_OUTPUT_INVALID_SCHEMA/)).toBeInTheDocument();
    expect(screen.queryByText("Built Python APIs")).not.toBeInTheDocument();
  });
});

function renderWithQuery(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>);
}
