import { describe, expect, it } from "vitest";

import {
  forwardedRequestHeaders,
  forwardedResponseHeaders,
  isAllowedBackendPath,
} from "@/lib/api/proxy-policy";

describe("backend proxy policy", () => {
  it("allows only authenticated CareerOps resource roots", () => {
    expect(isAllowedBackendPath(["api", "v1", "auth", "me"])).toBe(true);
    expect(isAllowedBackendPath(["api", "v1", "jobs", "job-id", "parse-runs"])).toBe(true);
    expect(isAllowedBackendPath(["api", "v1", "projects", "project-id", "checkpoints"])).toBe(true);
    expect(isAllowedBackendPath(["api", "v1", "auth", "login"])).toBe(false);
    expect(isAllowedBackendPath(["api", "v1", "admin"])).toBe(false);
    expect(isAllowedBackendPath(["api", "v1", "jobs", "..", "auth", "me"])).toBe(false);
  });

  it("injects authorization and forwards only contract headers", () => {
    const incoming = new Headers({
      "content-type": "application/json",
      "idempotency-key": "request-1",
      "if-match": "3",
      cookie: "must-not-forward=1",
      authorization: "Bearer attacker-token",
    });

    expect(Object.fromEntries(forwardedRequestHeaders(incoming, "trusted-token"))).toEqual({
      authorization: "Bearer trusted-token",
      "content-type": "application/json",
      "idempotency-key": "request-1",
      "if-match": "3",
    });
  });

  it("preserves retry and correlation headers without forwarding cookies", () => {
    const outgoing = forwardedResponseHeaders(
      new Headers({
        "content-type": "application/json",
        "retry-after": "43",
        "x-request-id": "request-id",
        "set-cookie": "backend-cookie=forbidden",
      }),
    );

    expect(Object.fromEntries(outgoing)).toEqual({
      "content-type": "application/json",
      "retry-after": "43",
      "x-request-id": "request-id",
    });
  });
});
