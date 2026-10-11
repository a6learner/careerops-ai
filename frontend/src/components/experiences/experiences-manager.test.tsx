import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { ExperiencesManager } from "@/components/experiences/experiences-manager";
import type { Experience } from "@/lib/api/types";

const experience: Experience = {
  id: "experience-id",
  title: "CareerOps AI",
  kind: "project",
  description: "Built a reliable backend.",
  skills: ["Python"],
  outcome: "Verified locally.",
  version: 4,
  content_hash: "hash",
  created_at: "2026-10-08T00:00:00Z",
  updated_at: "2026-10-08T00:00:00Z",
};

describe("ExperiencesManager", () => {
  it("creates an experience from the evidence form", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "POST") return Response.json(experience, { status: 201 });
      return Response.json({ items: [] });
    });
    const user = userEvent.setup();
    renderWithQuery(<ExperiencesManager />);

    await screen.findByText("Your evidence library is empty.");
    await user.click(screen.getByRole("button", { name: "Add experience" }));
    await user.type(screen.getByLabelText("Title"), "CareerOps AI");
    await user.type(screen.getByLabelText("What you did"), "Built a reliable backend.");
    await user.type(screen.getByLabelText("Skills"), "Python, python, FastAPI");
    await user.click(screen.getByRole("button", { name: "Add experience" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/api/v1/experiences",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          title: "CareerOps AI",
          kind: "project",
          description: "Built a reliable backend.",
          skills: ["Python", "FastAPI"],
          outcome: null,
        }),
      }),
    ));
  });

  it("uses the displayed version when editing", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "PATCH") return Response.json({ ...experience, title: "CareerOps Backend", version: 5 });
      return Response.json({ items: [experience] });
    });
    const user = userEvent.setup();
    renderWithQuery(<ExperiencesManager />);

    await screen.findByText("CareerOps AI");
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const title = screen.getByLabelText("Title");
    await user.clear(title);
    await user.type(title, "CareerOps Backend");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/api/v1/experiences/experience-id",
      expect.objectContaining({
        method: "PATCH",
        headers: expect.objectContaining({ "if-match": "4" }),
      }),
    ));
  });

  it("requires confirmation before deleting an experience", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "DELETE") return new Response(null, { status: 204 });
      return Response.json({ items: [experience] });
    });
    const user = userEvent.setup();
    renderWithQuery(<ExperiencesManager />);

    await screen.findByText("CareerOps AI");
    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("experience-id"),
      expect.objectContaining({ method: "DELETE" }),
    );
    await user.click(screen.getByRole("button", { name: "Confirm delete" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/api/v1/experiences/experience-id",
      { method: "DELETE" },
    ));
  });
});

function renderWithQuery(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>);
}
