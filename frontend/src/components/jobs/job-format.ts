import type { TagColor } from "@/components/ui/status-badge";
import type { JobStatus } from "@/lib/api/types";

const JOB_STATUS_COLORS: Record<JobStatus, TagColor> = {
  saved: "gray",
  preparing: "yellow",
  applied: "blue",
  interview: "purple",
  offer: "green",
  rejected: "red",
  withdrawn: "brown",
};

export function jobStatusTone(status: JobStatus): TagColor {
  return JOB_STATUS_COLORS[status];
}

export function formatDeadline(value: string): string {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}

export function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function daysUntil(deadline: string, now: Date = new Date()): number {
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  return Math.round((Date.parse(`${deadline}T00:00:00Z`) - today) / 86_400_000);
}

export function safeExternalUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}
