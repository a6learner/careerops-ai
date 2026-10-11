import Link from "next/link";

import { Card } from "@/components/ui/card";
import { ApiRequestError } from "@/lib/api/client";

type ApiFeedbackProps = {
  error: unknown;
  onRetry?: () => void;
};

export function ApiFeedback({ error, onRetry }: ApiFeedbackProps) {
  const content = describeError(error);
  return (
    <Card role="alert" className="border-rose-200 bg-[var(--danger-soft)] p-4">
      <p className="text-sm font-semibold text-[var(--danger)]">{content.title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-700">{content.message}</p>
      {error instanceof ApiRequestError ? (
        <p className="mt-2 text-xs text-slate-500">Request ID: {error.detail.request_id}</p>
      ) : null}
      <div className="mt-3 flex gap-3 text-sm font-semibold">
        {content.signIn ? (
          <Link className="text-[var(--brand)] hover:underline" href="/login?reason=expired">
            Sign in again
          </Link>
        ) : null}
        {onRetry ? (
          <button className="text-[var(--brand)] hover:underline" type="button" onClick={onRetry}>
            Try again
          </button>
        ) : null}
      </div>
    </Card>
  );
}

function describeError(error: unknown): { title: string; message: string; signIn: boolean } {
  if (!(error instanceof ApiRequestError)) {
    return {
      title: "Request failed",
      message: "CareerOps could not complete the request. Check the local services and try again.",
      signIn: false,
    };
  }

  if (error.status === 401) {
    return {
      title: "Session expired",
      message: "Your saved data is unchanged. Sign in again to continue.",
      signIn: true,
    };
  }
  if (error.status === 409) {
    return describeConflict(error);
  }
  if (error.status === 429) {
    return {
      title: "Too many requests",
      message: error.retryAfter
        ? `Wait ${error.retryAfter} seconds before trying again.`
        : "Wait briefly before trying again.",
      signIn: false,
    };
  }
  if (error.status === 503) {
    return {
      title: "Service unavailable",
      message: "A required local service is unavailable. Check the API, PostgreSQL, Redis, and worker, then retry.",
      signIn: false,
    };
  }

  return { title: "Request failed", message: error.detail.message, signIn: false };
}

function describeConflict(error: ApiRequestError): { title: string; message: string; signIn: false } {
  if (error.detail.code.endsWith("_VERSION_CONFLICT")) {
    return {
      title: "This record changed",
      message: "A newer version exists. Refresh the list before applying your change again.",
      signIn: false,
    };
  }
  if (error.detail.code === "PARSE_RUN_NOT_READY") {
    return { title: "Parsing is not ready", message: error.detail.message, signIn: false };
  }
  if (error.detail.code === "NO_ACTIVE_EXPERIENCES") {
    return { title: "Add experience evidence first", message: error.detail.message, signIn: false };
  }
  if (error.detail.code === "IDEMPOTENCY_KEY_CONFLICT") {
    return { title: "This request changed", message: error.detail.message, signIn: false };
  }
  if (error.detail.code === "ACTION_ITEM_SOURCE_NOT_ACTIONABLE") {
    return { title: "This gap is no longer actionable", message: error.detail.message, signIn: false };
  }
  return { title: "Request conflict", message: error.detail.message, signIn: false };
}
