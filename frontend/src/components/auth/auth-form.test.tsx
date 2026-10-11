import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthForm } from "@/components/auth/auth-form";

const replace = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, refresh }),
}));

afterEach(() => {
  vi.restoreAllMocks();
  replace.mockReset();
  refresh.mockReset();
});

describe("AuthForm", () => {
  it("signs in without exposing a bearer token to the component", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ authenticated: true }));
    const user = userEvent.setup();
    render(<AuthForm mode="login" />);

    await user.type(screen.getByLabelText("Email address"), "student@example.com");
    await user.type(screen.getByLabelText("Password"), "safe-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/session/login",
      expect.objectContaining({ method: "POST" }),
    );
    expect(replace).toHaveBeenCalledWith("/dashboard");
  });

  it("registers before creating the session", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ id: "user-id" }, { status: 201 }))
      .mockResolvedValueOnce(Response.json({ authenticated: true }));
    const user = userEvent.setup();
    render(<AuthForm mode="register" />);

    await user.type(screen.getByLabelText("Email address"), "student@example.com");
    await user.type(screen.getByLabelText("Password"), "safe-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/session/register",
      "/api/session/login",
    ]);
  });

  it("shows structured backend failures with their request id", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json(
        {
          error: {
            code: "INVALID_CREDENTIALS",
            message: "Email or password is incorrect.",
            details: {},
            request_id: "request-id",
          },
        },
        { status: 401 },
      ),
    );
    const user = userEvent.setup();
    render(<AuthForm mode="login" />);

    await user.type(screen.getByLabelText("Email address"), "student@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Email or password is incorrect. Request ID: request-id",
    );
    expect(replace).not.toHaveBeenCalled();
  });
});
