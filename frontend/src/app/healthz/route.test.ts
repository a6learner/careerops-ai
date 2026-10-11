import { describe, expect, it } from "vitest";

import { GET } from "./route";

describe("frontend liveness", () => {
  it("does not require downstream dependencies", async () => {
    const response = GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ status: "ok" });
  });
});
