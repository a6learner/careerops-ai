import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProjectsManager } from "@/components/projects/projects-manager";
import type { CheckpointRecord } from "@/lib/api/project-records";

const project = { id: "project-1", name: "Evidence project", goal: "Keep real decisions", created_at: "2026-10-27T00:00:00Z" };
const record: CheckpointRecord = {
  id: "record-1", project_id: project.id, status: "draft", version: 1,
  payload: {
    title: "Idempotent writes", objective: "Handle retries", changes: "Add a unique key",
    decisions: "Database uniqueness", failures: "", verification: "Client-supplied fixture",
    remaining: "MCP", contribution: "AI-proposed text", host: "test", base_revision: null,
    sources: [{ kind: "user_note", locator: "notes/stage.md", content: "Used unique keys.", quote: "unique keys" }],
  },
  content_sha256: "a".repeat(64), contribution_note: "", created_at: "2026-10-27T00:00:00Z", reviewed_at: null,
};

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ProjectsManager /></QueryClientProvider>);
}

describe("ProjectsManager", () => {
  it("requires personal contribution and sends displayed version when confirming", async () => {
    let current = { ...record };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (init?.method === "PATCH") {
        current = { ...current, status: "confirmed", version: 2, contribution_note: "I designed the constraint." };
        return Response.json(current);
      }
      return Response.json({ items: String(input).includes("checkpoints") ? [current] : [project], next_cursor: null });
    });
    const user = userEvent.setup(); mount();
    await user.click(await screen.findByRole("button", { name: project.name }));
    const confirm = await screen.findByRole("button", { name: "Confirm record" });
    expect(confirm).toBeDisabled();
    await user.type(screen.getByLabelText("Your actual contribution"), "I designed the constraint.");
    await user.click(confirm);
    await screen.findByText("confirmed · v2");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/api/v1/projects/project-1/checkpoints/record-1/review",
      expect.objectContaining({ method: "PATCH", headers: { "content-type": "application/json", "if-match": "1" },
        body: JSON.stringify({ status: "confirmed", contribution_note: "I designed the constraint." }) }),
    );
  });

  it("keeps the same submission key after a lost response", async () => {
    const attempts: RequestInit[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (init?.method === "POST") {
        attempts.push(init);
        if (attempts.length === 1) throw new TypeError("Lost response");
        return Response.json(project);
      }
      return Response.json({ items: String(input).includes("checkpoints") ? [] : [project], next_cursor: null });
    });
    const user = userEvent.setup(); mount();
    await user.type(screen.getByLabelText("Project name"), "Evidence project");
    await user.type(screen.getByLabelText("Project goal"), "Keep real decisions");
    await user.click(screen.getByRole("button", { name: "Create project" }));
    await screen.findByRole("alert");
    await user.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() => expect(attempts).toHaveLength(2));
    expect(attempts[0].headers).toEqual(attempts[1].headers);
    expect(attempts[0].body).toEqual(attempts[1].body);
  });

  it("shows withdrawn history without a confirm or withdraw action", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => Response.json({
      items: String(input).includes("checkpoints") ? [{ ...record, status: "withdrawn", version: 3 }] : [project], next_cursor: null,
    }));
    const user = userEvent.setup(); mount();
    await user.click(await screen.findByRole("button", { name: project.name }));
    await screen.findByText(/Withdrawn: keep for history/);
    expect(screen.queryByRole("button", { name: "Confirm record" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Withdraw record" })).not.toBeInTheDocument();
    await user.click(screen.getByText("Record details and sources"));
    expect(screen.getByText("unique keys", { selector: "blockquote" })).toBeInTheDocument();
  });
});
