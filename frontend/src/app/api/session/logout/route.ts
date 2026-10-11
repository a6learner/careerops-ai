import { cookies } from "next/headers";

import { isTrustedMutationRequest, SESSION_COOKIE_NAME } from "@/lib/auth/session";

export async function POST(request: Request): Promise<Response> {
  if (!isTrustedMutationRequest(request)) {
    return Response.json({ error: { message: "Untrusted request origin." } }, { status: 403 });
  }

  (await cookies()).delete(SESSION_COOKIE_NAME);
  return new Response(null, { status: 204 });
}
