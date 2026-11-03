import { CircleAlert } from "lucide-react";

import type { BadgeTone } from "@/components/ui/status-badge";
import type { ParseRunStatus } from "@/lib/api/types";
import { describeRunError } from "@/lib/run-errors";

export const TERMINAL_RUN_STATUSES = new Set<ParseRunStatus>(["succeeded", "failed", "cancelled"]);

export function runStatusTone(status: ParseRunStatus): BadgeTone {
  if (status === "succeeded") return "green";
  if (status === "failed") return "red";
  if (status === "cancelled") return "gray";
  return status === "running" ? "blue" : "yellow";
}

export function humanize(value: string): string {
  return value.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

export function RunFailure({ code, consequence }: { code: string | null; consequence: string }) {
  return (
    <div className="flex gap-3 rounded-md bg-danger-soft px-4 py-3.5 text-sm">
      <CircleAlert className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden="true" />
      <div>
        <p className="text-foreground/85">{describeRunError(code)} {consequence}</p>
        <p className="mt-1 font-mono text-[11px] text-muted">code: {code ?? "UNKNOWN"}</p>
      </div>
    </div>
  );
}
