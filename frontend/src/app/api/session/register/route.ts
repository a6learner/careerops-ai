import { buildBackendUrl } from "@/lib/api/config";
import { dependencyUnavailableResponse } from "@/lib/api/errors";
import { isTrustedMutationRequest } from "@/lib/auth/session";

export async function POST(request: Request): Promise<Response> {
  if (!isTrustedMutationRequest(request)) {
    return Response.json({ error: { message: "Untrusted request origin." } }, { status: 403 });
  }

  try {
    const backendResponse = await fetch(buildBackendUrl("/api/v1/auth/register"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await request.text(),
      cache: "no-store",
    });
    return new Response(await backendResponse.text(), {
      status: backendResponse.status,
      headers: {
        "content-type": backendResponse.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return dependencyUnavailableResponse();
  }
}
