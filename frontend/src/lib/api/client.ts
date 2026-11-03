import { readApiError, type ApiErrorDetail } from "@/lib/api/errors";

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: ApiErrorDetail,
    public readonly retryAfter: string | null,
  ) {
    super(detail.message);
    this.name = "ApiRequestError";
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/backend${path}`, init);
  if (!response.ok) {
    throw new ApiRequestError(
      response.status,
      await readApiError(response),
      response.headers.get("retry-after"),
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

// Resolves to null only for the named not-found code, so an unowned parent (JOB_NOT_FOUND) still surfaces.
export async function apiRequestOrNull<T>(path: string, absentCode: string): Promise<T | null> {
  try {
    return await apiRequest<T>(path);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404 && error.detail.code === absentCode) {
      return null;
    }
    throw error;
  }
}
