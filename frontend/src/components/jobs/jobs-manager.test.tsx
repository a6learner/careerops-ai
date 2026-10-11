import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { JobsManager } from "@/components/jobs/jobs-manager";
import type { Job } from "@/lib/api/types";

const job: Job = {
  id: "job-id",
  company: "Example Corp",
  title: "Backend Engineer Intern",
  raw_description: "Build reliable APIs.",
  description_hash: "hash",
  source_url: null,
  location: "Los Angeles",
  deadline: null,
  status: "saved",
  version: 2,
  created_at: "2026-10-08T00:00:00Z",
  updated_at: "2026-10-08T00:00:00Z",
};

describe("JobsManager", () => {
  it("creates a job from the target-role form", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "POST") return Response.json(job, { status: 201 });
      return Response.json({ items: [], next_cursor: null });
    });
    const user = userEvent.setup();
    renderWithQuery(<JobsManager />);

    await screen.findByText("No jobs in this view.");
    await user.click(screen.getByRole("button", { name: "Add job" }));
    await user.type(screen.getByLabelText("Company"), "Example Corp");
    await user.type(screen.getByLabelText("Role"), "Backend Engineer Intern");
    await user.type(screen.getByLabelText("Job description"), "Build reliable APIs.");
    await user.click(screen.getByRole("button", { name: "Save job" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/api/v1/jobs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          company: "Example Corp",
          title: "Backend Engineer Intern",
          raw_description: "Build reliable APIs.",
          source_url: null,
          location: null,
          deadline: null,
          status: "saved",
        }),
      }),
    ));
  });

  it("updates status with optimistic locking", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "PATCH") return Response.json({ ...job, status: "applied", version: 3 });
      return Response.json({ items: [job], next_cursor: null });
    });
    const user = userEvent.setup();
    renderWithQuery(<JobsManager />);

    await screen.findByText("Backend Engineer Intern");
    await user.selectOptions(screen.getByLabelText("Update status"), "applied");
    await user.click(screen.getByRole("button", { name: "Update" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/api/v1/jobs/job-id",
      expect.objectContaining({
        method: "PATCH",
        headers: expect.objectContaining({ "if-match": "2" }),
        body: JSON.stringify({ status: "applied" }),
      }),
    ));
  });
});

function renderWithQuery(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>);
}
