import { describe, expect, it } from "vitest";

import { readApiError } from "@/lib/api/errors";

describe("API error parsing", () => {
  it("keeps the backend error code and request id", async () => {
    const response = Response.json(
      {
        error: {
          code: "ANALYSIS_RATE_LIMITED",
          message: "Try later.",
          details: { retry_after_seconds: 43 },
          request_id: "request-id",
        },
      },
      { status: 429 },
    );

    await expect(readApiError(response)).resolves.toEqual({
      code: "ANALYSIS_RATE_LIMITED",
      message: "Try later.",
      details: { retry_after_seconds: 43 },
      request_id: "request-id",
    });
  });

  it("returns a safe fallback for an unexpected response", async () => {
    const response = new Response("not-json", {
      status: 502,
      headers: { "x-request-id": "proxy-id" },
    });

    await expect(readApiError(response)).resolves.toMatchObject({
      code: "UNEXPECTED_RESPONSE",
      request_id: "proxy-id",
    });
  });
});
