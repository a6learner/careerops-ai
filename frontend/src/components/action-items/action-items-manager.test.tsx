import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { ActionItemsManager } from "@/components/action-items/action-items-manager";
import type { ActionItem, Job } from "@/lib/api/types";

const job: Job = { id: "job-id", company: "Example", title: "Backend Intern", raw_description: "Build APIs", description_hash: "hash", source_url: null, location: null, deadline: null, status: "saved", version: 1, created_at: "", updated_at: "" };
const item: ActionItem = { id: "item-id", job_id: job.id, source_evidence_match_id: null, title: "Practice APIs", status: "todo", version: 3, job_is_archived: false, created_at: "", updated_at: "" };

describe("ActionItemsManager", () => {
  it("creates a manual action item with an idempotency key", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/api/v1/jobs")) return Response.json({ items: [job], next_cursor: null });
      if (init?.method === "POST") return Response.json(item, { status: 201 });
      return Response.json({ items: [], next_cursor: null });
    });
    const user = userEvent.setup();
    renderWithQuery(<ActionItemsManager />);

    await screen.findByText("No action items in this view.");
    await user.click(screen.getByRole("button", { name: "Add action item" }));
    await user.selectOptions(screen.getByLabelText("Job"), job.id);
    await user.type(screen.getByLabelText("Task"), "Practice APIs");
    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/api/v1/action-items",
      expect.objectContaining({ method: "POST", headers: expect.objectContaining({ "idempotency-key": expect.any(String) }) }),
    ));
  });

  it("reuses the creation key when the same submission is retried", async () => {
    const keys: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/api/v1/jobs")) return Response.json({ items: [job], next_cursor: null });
      if (init?.method === "POST") {
        keys.push(new Headers(init.headers).get("idempotency-key") ?? "");
        if (keys.length === 1) return Response.json({ error: { code: "DEPENDENCY_UNAVAILABLE", message: "Unavailable", details: {}, request_id: "request-id" } }, { status: 503 });
        return Response.json(item, { status: 201 });
      }
      return Response.json({ items: [], next_cursor: null });
    });
    const user = userEvent.setup();
    renderWithQuery(<ActionItemsManager />);

    await screen.findByText("No action items in this view.");
    await user.click(screen.getByRole("button", { name: "Add action item" }));
    await user.selectOptions(screen.getByLabelText("Job"), job.id);
    await user.type(screen.getByLabelText("Task"), "Practice APIs");
    await user.click(screen.getByRole("button", { name: "Create" }));
    await screen.findByText("Service unavailable");
    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(keys).toHaveLength(2));
    expect(keys[0]).toBeTruthy();
    expect(keys[1]).toBe(keys[0]);
  });

  it("updates title and status with the displayed version", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/api/v1/jobs")) return Response.json({ items: [job], next_cursor: null });
      if (init?.method === "PATCH") return Response.json({ ...item, title: "Practice systems design", status: "doing", version: 4 });
      return Response.json({ items: [item], next_cursor: null });
    });
    const user = userEvent.setup();
    renderWithQuery(<ActionItemsManager />);

    const title = await screen.findByLabelText("Action item title");
    await user.clear(title);
    await user.type(title, "Practice systems design");
    await user.selectOptions(screen.getByLabelText("Status", { selector: "#action-status-item-id" }), "doing");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/api/v1/action-items/item-id",
      expect.objectContaining({ method: "PATCH", headers: expect.objectContaining({ "if-match": "3" }) }),
    ));
  });
});

function renderWithQuery(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>);
}
