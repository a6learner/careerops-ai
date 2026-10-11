import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { ParseRunPanel } from "@/components/jobs/parse-run-panel";
import type { Job, ParseRun } from "@/lib/api/types";

const job: Job = {
  id: "job-id",
  company: "Example Corp",
  title: "Backend Engineer Intern",
  raw_description: "Python experience required.",
  description_hash: "hash",
  source_url: null,
  location: null,
  deadline: null,
  status: "saved",
  version: 1,
  created_at: "2026-10-10T00:00:00Z",
  updated_at: "2026-10-10T00:00:00Z",
};

const queuedRun: ParseRun = {
  id: "parse-run-id",
  job_id: job.id,
  status: "queued",
  idempotency_key: "key",
  input_fingerprint: "fingerprint",
  model_name: "local-fake-parser",
  prompt_version: "parse-v2",
  attempt: 1,
  error_code: null,
  latency_ms: null,
  input_tokens: null,
  output_tokens: null,
  started_at: null,
  finished_at: null,
  created_at: "2026-10-10T00:00:00Z",
  requirements: [],
};

describe("ParseRunPanel", () => {
  it("reuses the idempotency key when a submission is retried", async () => {
    const postKeys: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "POST") {
        postKeys.push(new Headers(init.headers).get("idempotency-key") ?? "");
        if (postKeys.length === 1) {
          return apiError(503, "DEPENDENCY_UNAVAILABLE", "Worker unavailable.");
        }
        return Response.json(queuedRun, { status: 202 });
      }
      return Response.json({ ...queuedRun, status: "running", started_at: "2026-10-10T00:00:01Z" });
    });
    const user = userEvent.setup();
    renderWithQuery(<ParseRunPanel job={job} />);

    await user.click(screen.getByRole("button", { name: "Parse description" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Service unavailable");
    await user.click(screen.getByRole("button", { name: "Try again" }));

    await screen.findByText("Running");
    expect(postKeys).toHaveLength(2);
    expect(postKeys[0]).toBeTruthy();
    expect(postKeys[1]).toBe(postKeys[0]);
  });

  it("shows requirements returned by a completed parse", async () => {
    const succeededRun: ParseRun = {
      ...queuedRun,
      status: "succeeded",
      finished_at: "2026-10-10T00:00:02Z",
      requirements: [
        {
          id: "requirement-id",
          category: "must_have",
          text: "Python experience required.",
          skill_normalized: "python",
          source_span_start: 0,
          source_span_end: 27,
        },
      ],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json(succeededRun, { status: 202 }));
    const user = userEvent.setup();
    renderWithQuery(<ParseRunPanel job={job} />);

    await user.click(screen.getByRole("button", { name: "Parse description" }));

    expect(await screen.findByText("Succeeded")).toBeInTheDocument();
    expect(screen.getByText("Must Have")).toBeInTheDocument();
    expect(screen.getByText("Python experience required.")).toBeInTheDocument();
  });

  it("shows a durable parse failure without inventing requirements", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ ...queuedRun, status: "failed", error_code: "PARSER_OUTPUT_INVALID" }, { status: 202 }),
    );
    const user = userEvent.setup();
    renderWithQuery(<ParseRunPanel job={job} />);

    await user.click(screen.getByRole("button", { name: "Parse description" }));

    expect(await screen.findByText("Failed")).toBeInTheDocument();
    expect(screen.getByText(/PARSER_OUTPUT_INVALID/)).toBeInTheDocument();
    expect(screen.queryByText("Must Have")).not.toBeInTheDocument();
  });
});

function apiError(status: number, code: string, message: string): Response {
  return Response.json(
    { error: { code, message, details: {}, request_id: "request-id" } },
    { status },
  );
}

function renderWithQuery(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>);
}
