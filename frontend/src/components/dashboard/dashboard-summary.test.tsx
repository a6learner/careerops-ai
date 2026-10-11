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

    expect(await screen.findByText("Active jobs")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getAllByText("2")).toHaveLength(4);
  });
});
