import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { JobDetail } from "@/components/jobs/job-detail";
import type { Job } from "@/lib/api/types";

const job: Job = {
  id: "job-id", company: "Northwind", title: "Backend Intern", raw_description: "Build APIs.",
  description_hash: "hash", source_url: "javascript:alert(1)", location: null, deadline: null,
  status: "interview", version: 4, created_at: "2026-10-10T00:00:00Z", updated_at: "2026-10-10T00:00:00Z",
};

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><JobDetail jobId="job-id" /></QueryClientProvider>);
}

describe("JobDetail", () => {
  it("renders job properties and never links an unsafe source URL", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/parse-runs/latest")) {
        return Response.json({ error: { code: "PARSE_RUN_NOT_FOUND", message: "", details: {}, request_id: "r" } }, { status: 404 });
      }
      return Response.json(job);
    });
    mount();

    expect(await screen.findByRole("heading", { name: "Backend Intern", level: 1 })).toBeInTheDocument();
    expect(screen.getByLabelText("Update status")).toHaveValue("interview");
    expect(screen.queryByRole("link", { name: /alert/ })).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Parse description" })).toBeInTheDocument();
  });

  it("explains a missing or foreign job instead of showing an error dump", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      Response.json({ error: { code: "JOB_NOT_FOUND", message: "Job was not found.", details: {}, request_id: "r" } }, { status: 404 }),
    );
    mount();

    expect(await screen.findByText("Job not found")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /All jobs/ })).toHaveAttribute("href", "/jobs");
  });
});
