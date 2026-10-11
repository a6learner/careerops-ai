import "server-only";

import { cookies } from "next/headers";

import { buildBackendUrl } from "@/lib/api/config";
import { SESSION_COOKIE_NAME } from "@/lib/auth/session";

export type CurrentUser = {
  id: string;
  email: string;
  created_at: string;
};

export type CurrentUserResult =
  | { kind: "authenticated"; user: CurrentUser }
  | { kind: "unauthenticated" }
  | { kind: "unavailable" };

function isCurrentUser(value: unknown): value is CurrentUser {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "string" &&
    "email" in value &&
    typeof value.email === "string" &&
    "created_at" in value &&
    typeof value.created_at === "string"
  );
}

export async function getCurrentUser(): Promise<CurrentUserResult> {
  const token = (await cookies()).get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return { kind: "unauthenticated" };
  }

  try {
    const response = await fetch(buildBackendUrl("/api/v1/auth/me"), {
      headers: { authorization: `Bearer ${token}` },
      cache: "no-store",
    });

    if (response.status === 401) {
      return { kind: "unauthenticated" };
    }
    if (!response.ok) {
      return { kind: "unavailable" };
    }

    const body: unknown = await response.json();
    return isCurrentUser(body)
      ? { kind: "authenticated", user: body }
      : { kind: "unavailable" };
  } catch {
    return { kind: "unavailable" };
  }
}
