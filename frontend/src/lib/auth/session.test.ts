import { describe, expect, it } from "vitest";

import {
  isTrustedMutationRequest,
  SESSION_MAX_AGE_SECONDS,
  sessionCookieOptions,
} from "@/lib/auth/session";

describe("session security", () => {
  it("uses an HttpOnly same-site cookie aligned with the backend token lifetime", () => {
    expect(sessionCookieOptions(false)).toEqual({
      httpOnly: true,
      sameSite: "lax",
      secure: false,
      path: "/",
      maxAge: SESSION_MAX_AGE_SECONDS,
    });
    expect(sessionCookieOptions(true).secure).toBe(true);
  });

  it("accepts only same-origin mutation requests", () => {
    expect(
      isTrustedMutationRequest(
        new Request("http://localhost:3000/api/session/login", {
          headers: { origin: "http://localhost:3000" },
        }),
      ),
    ).toBe(true);
    expect(
      isTrustedMutationRequest(
        new Request("http://localhost:3000/api/session/login", {
          headers: { origin: "https://attacker.example" },
        }),
      ),
    ).toBe(false);
    expect(
      isTrustedMutationRequest(new Request("http://localhost:3000/api/session/login")),
    ).toBe(false);
  });

  it("uses the explicit public origin when the container listener is internal", () => {
    const internalRequest = new Request("http://0.0.0.0:3000/api/session/login", {
      headers: { origin: "http://127.0.0.1:13010" },
    });

    expect(isTrustedMutationRequest(internalRequest, "http://127.0.0.1:13010")).toBe(true);
    expect(isTrustedMutationRequest(internalRequest, "http://127.0.0.1:3000")).toBe(false);
    expect(isTrustedMutationRequest(internalRequest, "not-a-url")).toBe(false);
  });
});
