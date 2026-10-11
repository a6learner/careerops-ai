import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

describe("frontend readiness", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("is ready only when the backend readiness endpoint succeeds", async () => {
    const backendFetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", backendFetch);

    const response = await GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ status: "ready", api: true });
    expect(backendFetch).toHaveBeenCalledWith(
      new URL("http://127.0.0.1:8000/readyz"),
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it.each([new Response(null, { status: 503 }), new Error("unreachable")])(
    "returns 503 without leaking backend details",
    async (outcome) => {
      const backendFetch = vi.fn();
      if (outcome instanceof Error) {
        backendFetch.mockRejectedValue(outcome);
      } else {
        backendFetch.mockResolvedValue(outcome);
      }
      vi.stubGlobal("fetch", backendFetch);

      const response = await GET();

      expect(response.status).toBe(503);
      await expect(response.json()).resolves.toEqual({ status: "not_ready", api: false });
    },
  );
});
