import { cookies } from "next/headers";

import { buildBackendUrl } from "@/lib/api/config";
import { dependencyUnavailableResponse } from "@/lib/api/errors";
import {
  forwardedRequestHeaders,
  forwardedResponseHeaders,
  isAllowedBackendPath,
} from "@/lib/api/proxy-policy";
import { isTrustedMutationRequest, SESSION_COOKIE_NAME } from "@/lib/auth/session";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxyRequest(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  if (!isAllowedBackendPath(path)) {
    return Response.json({ error: { message: "Route is not available." } }, { status: 404 });
  }

  if (!["GET", "HEAD"].includes(request.method) && !isTrustedMutationRequest(request)) {
    return Response.json({ error: { message: "Untrusted request origin." } }, { status: 403 });
  }

  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return Response.json(
      {
        error: {
          code: "TOKEN_MISSING",
          message: "Authentication is required.",
          details: {},
          request_id: crypto.randomUUID(),
        },
      },
      { status: 401 },
    );
  }

  try {
    const requestUrl = new URL(request.url);
    const backendUrl = buildBackendUrl(`/${path.join("/")}`, requestUrl.search);
    const hasBody = !["GET", "HEAD"].includes(request.method);
    const backendResponse = await fetch(backendUrl, {
      method: request.method,
      headers: forwardedRequestHeaders(request.headers, token),
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
    });

    if (backendResponse.status === 401) {
      cookieStore.delete(SESSION_COOKIE_NAME);
    }

    return new Response(await backendResponse.arrayBuffer(), {
      status: backendResponse.status,
      headers: forwardedResponseHeaders(backendResponse.headers),
    });
  } catch {
    return dependencyUnavailableResponse();
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
