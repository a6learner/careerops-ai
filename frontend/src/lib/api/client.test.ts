import { describe, expect, it, vi } from "vitest";

import { ApiRequestError, apiRequest } from "@/lib/api/client";

describe("apiRequest", () => {
  it("preserves the structured error and retry delay", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json(
        {
          error: {
            code: "RATE_LIMIT_EXCEEDED",
            message: "Try later.",
            details: {},
            request_id: "request-429",
          },
        },
        { status: 429, headers: { "retry-after": "30" } },
      ),
    );

    const error = await apiRequest("/api/v1/jobs").catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect(error).toMatchObject({
      status: 429,
      retryAfter: "30",
      detail: { code: "RATE_LIMIT_EXCEEDED", request_id: "request-429" },
    });
  });
});
