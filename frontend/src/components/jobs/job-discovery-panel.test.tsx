import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { JobDiscoveryPanel } from "@/components/jobs/job-discovery-panel";

describe("JobDiscoveryPanel", () => {
  it("submits search criteria and exposes source freshness", async () => {
    const run = {
      id: "run-1",
      status: "succeeded",
      query: "Backend Engineer",
      location: "Los Angeles",
      remote: null,
      published_within_days: 14,
      query_fingerprint: "a".repeat(64),
      provider_name: "fake-search-v1",
      attempt: 1,
      error_code: null,
      started_at: "2026-10-11T00:00:00Z",
      finished_at: "2026-10-11T00:00:01Z",
      created_at: "2026-10-11T00:00:00Z",
      results: [{
        id: "result-1",
        provider_result_id: "fake-1",
        company: "Example Systems",
        title: "Backend Engineer Intern",
        source_url: "https://jobs.example.test/1",
        summary: "Synthetic result.",
        raw_description: null,
        location: "Los Angeles",
        published_at: null,
        observed_at: "2026-10-11T00:00:01Z",
      }],
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async () => Response.json(run));
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><JobDiscoveryPanel /></QueryClientProvider>);

    await user.type(screen.getByLabelText("Keywords"), "Backend Engineer");
    await user.type(screen.getByLabelText("Location"), "Los Angeles");
    await user.type(screen.getByLabelText("Published within days"), "14");
    await user.click(screen.getByRole("button", { name: "Search jobs" }));

    await screen.findByText("Backend Engineer Intern");
    expect(screen.getByText(/Description required/)).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/api/v1/job-discovery-runs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          query: "Backend Engineer",
          location: "Los Angeles",
          remote: null,
          published_within_days: 14,
        }),
      }),
    ));
  });
});
