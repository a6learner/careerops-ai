import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardFocus } from "@/components/dashboard/dashboard-focus";
import type { DashboardFocus as DashboardFocusData } from "@/lib/api/types";

const focus: DashboardFocusData = {
  generated_at: "2026-10-29T12:00:00Z",
  today: "2026-10-29",
  upcoming_deadlines: [
    { id: "job-soon", company: "Northwind", title: "Backend Intern", status: "applied", deadline: "2026-11-01", updated_at: "2026-10-28T00:00:00Z" },
  ],
  recent_jobs: [
    { id: "job-soon", company: "Northwind", title: "Backend Intern", status: "applied", deadline: "2026-11-01", updated_at: "2026-10-28T00:00:00Z" },
  ],
  open_action_items: [],
};

describe("DashboardFocus", () => {
  it("links deadlines to their job pages and shows empty sections plainly", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => Response.json(focus));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><DashboardFocus /></QueryClientProvider>);

    const deadlines = await screen.findByRole("region", { name: "Upcoming deadlines" });
    const link = await within(deadlines).findByRole("link", { name: /Backend Intern/ });
    expect(link).toHaveAttribute("href", "/jobs/job-soon");
    // Days are counted from the server's date, not the browser clock.
    expect(within(deadlines).getByText("Nov 1, 2026 · 3d")).toBeInTheDocument();
    expect(screen.getByText("No open action items.")).toBeInTheDocument();
  });
});
