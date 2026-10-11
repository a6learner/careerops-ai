import { buildBackendUrl } from "@/lib/api/config";

const READINESS_TIMEOUT_MS = 2_000;

export async function GET(): Promise<Response> {
  try {
    const response = await fetch(buildBackendUrl("/readyz"), {
      cache: "no-store",
      signal: AbortSignal.timeout(READINESS_TIMEOUT_MS),
    });
    if (!response.ok) {
      return notReady();
    }
    return Response.json({ status: "ready", api: true });
  } catch {
    return notReady();
  }
}

function notReady(): Response {
  return Response.json({ status: "not_ready", api: false }, { status: 503 });
}
