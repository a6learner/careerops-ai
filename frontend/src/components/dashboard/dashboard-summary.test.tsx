import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardSummary } from "@/components/dashboard/dashboard-summary";

describe("DashboardSummary", () => {
  it("renders counts returned by the dashboard API", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({
      generated_at: "2026-10-10T12:00:00Z",
      jobs: { total: 6, saved: 2, preparing: 1, applied: 2, interview: 1, offer: 0, rejected: 0, withdrawn: 0 },
      action_items: { total: 5, todo: 2, doing: 1, done: 2 },
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><DashboardSummary /></QueryClientProvider>);

    expect(await screen.findByText("Tracked jobs")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
    // Submitted counts every job past "applied" (2 + 1 + 0); open tasks are todo + doing (2 + 1).
    expect(screen.getAllByText("3")).toHaveLength(2);
    expect(screen.getByText("40% of 5 tasks")).toBeInTheDocument();
    expect(screen.getByRole("img", {
      name: "Saved 2, Preparing 1, Applied 2, Interview 1, Offer 0, Rejected 0, Withdrawn 0",
    })).toBeInTheDocument();
  });
});
