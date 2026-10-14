import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CvImportPanel } from "@/components/experiences/cv-import-panel";

describe("CvImportPanel", () => {
  it("uploads a supported file and shows reviewable drafts", async () => {
    const record = {
      id: "import-1",
      status: "succeeded",
      filename: "resume.md",
      document_type: "markdown",
      media_type: "text/markdown",
      size_bytes: 20,
      content_sha256: "a".repeat(64),
      extractor_name: "deterministic-extractive-v1",
      attempt: 1,
      error_code: null,
      started_at: "2026-10-11T00:00:00Z",
      finished_at: "2026-10-11T00:00:01Z",
      created_at: "2026-10-11T00:00:00Z",
      drafts: [{
        id: "draft-1",
        cv_import_id: "import-1",
        status: "pending",
        title: "CareerOps AI",
        kind: "other",
        description: "Built reliable services.",
        skills: [],
        outcome: null,
        source_refs: [{ field: "source_block", start: 0, end: 36, quote: "CareerOps AI\nBuilt reliable services." }],
        version: 1,
        confirmed_experience_id: null,
        created_at: "2026-10-11T00:00:01Z",
        updated_at: "2026-10-11T00:00:01Z",
      }],
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async () => Response.json(record));
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><CvImportPanel /></QueryClientProvider>);

    await user.upload(screen.getByLabelText("Choose CV"), new File(["CareerOps AI"], "resume.md", { type: "text/markdown" }));

    await screen.findByDisplayValue("CareerOps AI");
    expect(screen.getByText("Built reliable services.")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/api/v1/cv-imports",
      expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
    ));
  });
});
