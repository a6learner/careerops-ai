import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiFeedback } from "@/components/api-feedback";
import { ApiRequestError } from "@/lib/api/client";

describe("ApiFeedback", () => {
  it("distinguishes an analysis precondition conflict from a stale record", () => {
    render(<ApiFeedback error={apiError(409, "NO_ACTIVE_EXPERIENCES", "Create an experience before analysis.")} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Add experience evidence first");
    expect(screen.getByRole("alert")).toHaveTextContent("Create an experience before analysis.");
  });

  it("shows the server retry delay for rate limiting", () => {
    render(<ApiFeedback error={apiError(429, "ANALYSIS_RATE_LIMITED", "Too many runs.", "43")} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Too many requests");
    expect(screen.getByRole("alert")).toHaveTextContent("Wait 43 seconds");
  });
});

function apiError(status: number, code: string, message: string, retryAfter: string | null = null) {
  return new ApiRequestError(status, { code, message, details: {}, request_id: "request-id" }, retryAfter);
}
