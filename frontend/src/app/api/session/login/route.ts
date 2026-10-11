import { cookies } from "next/headers";

import { buildBackendUrl } from "@/lib/api/config";
import { dependencyUnavailableResponse } from "@/lib/api/errors";
import {
  isTrustedMutationRequest,
  SESSION_COOKIE_NAME,
  sessionCookieOptions,
} from "@/lib/auth/session";

type AccessTokenResponse = {
  access_token: string;
  token_type: string;
};

function isAccessTokenResponse(value: unknown): value is AccessTokenResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "access_token" in value &&
    typeof value.access_token === "string" &&
    "token_type" in value &&
    value.token_type === "bearer"
  );
}

export async function POST(request: Request): Promise<Response> {
  if (!isTrustedMutationRequest(request)) {
    return Response.json({ error: { message: "Untrusted request origin." } }, { status: 403 });
  }

  try {
    const backendResponse = await fetch(buildBackendUrl("/api/v1/auth/login"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await request.text(),
      cache: "no-store",
    });

    if (!backendResponse.ok) {
      return new Response(await backendResponse.text(), {
        status: backendResponse.status,
        headers: {
          "content-type": backendResponse.headers.get("content-type") ?? "application/json",
        },
      });
    }

    const body: unknown = await backendResponse.json();
    if (!isAccessTokenResponse(body)) {
      return dependencyUnavailableResponse();
    }

    (await cookies()).set(
      SESSION_COOKIE_NAME,
      body.access_token,
      sessionCookieOptions(process.env.NODE_ENV === "production"),
    );
    return Response.json({ authenticated: true });
  } catch {
    return dependencyUnavailableResponse();
  }
}
