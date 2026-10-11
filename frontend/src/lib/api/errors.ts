export type ApiErrorDetail = {
  code: string;
  message: string;
  details: Record<string, unknown>;
  request_id: string;
};

export type ApiErrorResponse = {
  error: ApiErrorDetail;
};

export function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }

  const error = value.error;
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    typeof error.code === "string" &&
    "message" in error &&
    typeof error.message === "string" &&
    "request_id" in error &&
    typeof error.request_id === "string"
  );
}

export async function readApiError(response: Response): Promise<ApiErrorDetail> {
  try {
    const body: unknown = await response.json();
    if (isApiErrorResponse(body)) {
      return body.error;
    }
  } catch {
    // The fallback below keeps unexpected proxy responses user-safe.
  }

  return {
    code: "UNEXPECTED_RESPONSE",
    message: "The request could not be completed.",
    details: {},
    request_id: response.headers.get("x-request-id") ?? "not-available",
  };
}

export function dependencyUnavailableResponse(): Response {
  return Response.json(
    {
      error: {
        code: "DEPENDENCY_UNAVAILABLE",
        message: "The CareerOps API is unavailable.",
        details: {},
        request_id: crypto.randomUUID(),
      },
    } satisfies ApiErrorResponse,
    { status: 503 },
  );
}
