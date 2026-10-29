"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarClock, CircleDashed, History, type LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { statusLabel } from "@/components/jobs/job-create-form";
import { daysUntil, formatDeadline, formatTimestamp, jobStatusTone } from "@/components/jobs/job-format";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api/client";
import type { DashboardFocus as DashboardFocusData } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function DashboardFocus() {
  const focus = useQuery({
    queryKey: ["dashboard", "focus"],
    queryFn: () => apiRequest<DashboardFocusData>("/api/v1/dashboard/focus"),
  });

  if (focus.error) {
    return <div className="mt-10"><ApiFeedback error={focus.error} onRetry={() => void focus.refetch()} /></div>;
  }

  const data = focus.data;
  const today = data ? new Date(`${data.today}T00:00:00Z`) : undefined;

  return (
    <div className="mt-10 grid gap-x-10 gap-y-10 lg:grid-cols-2">
      <FocusSection icon={CalendarClock} title="Upcoming deadlines" isLoading={focus.isPending} empty="No open roles with a deadline ahead.">
        {data?.upcoming_deadlines.map((job) => {
          const days = job.deadline ? daysUntil(job.deadline, today) : null;
          return (
            <FocusRow key={job.id} href={`/jobs/${job.id}`} title={job.title} meta={job.company}>
              {job.deadline ? (
                <span className={cn("text-xs tabular-nums", days !== null && days <= 7 ? "font-medium text-[var(--tag-red-fg)]" : "text-muted")}>
                  {days === 0 ? "Today" : `${formatDeadline(job.deadline)} · ${days}d`}
                </span>
              ) : null}
            </FocusRow>
          );
        })}
      </FocusSection>

      <FocusSection icon={CircleDashed} title="Next tasks" isLoading={focus.isPending} empty="No open action items.">
        {data?.open_action_items.map((item) => (
          <FocusRow key={item.id} href={`/jobs/${item.job_id}`} title={item.title} meta={`${item.job_company} · ${item.job_title}`}>
            <StatusBadge tone={item.status === "doing" ? "blue" : "gray"}>{item.status === "doing" ? "Doing" : "To do"}</StatusBadge>
          </FocusRow>
        ))}
      </FocusSection>

      <FocusSection icon={History} title="Recently updated" isLoading={focus.isPending} empty="No jobs yet." className="lg:col-span-2">
        {data?.recent_jobs.map((job) => (
          <FocusRow key={job.id} href={`/jobs/${job.id}`} title={job.title} meta={`${job.company} · ${formatTimestamp(job.updated_at)}`}>
            <StatusBadge tone={jobStatusTone(job.status)}>{statusLabel(job.status)}</StatusBadge>
          </FocusRow>
        ))}
      </FocusSection>
    </div>
  );
}

type FocusSectionProps = {
  icon: LucideIcon;
  title: string;
  isLoading: boolean;
  empty: string;
  className?: string;
  children?: ReactNode[];
};

function FocusSection({ icon: Icon, title, isLoading, empty, className, children }: FocusSectionProps) {
  const hasRows = Array.isArray(children) && children.length > 0;
  return (
    <section className={className} aria-label={title}>
      <h2 className="flex items-center gap-2 border-b pb-2 text-lg font-semibold">
        <Icon className="size-[18px] text-faint" strokeWidth={1.75} aria-hidden="true" />
        {title}
      </h2>
      {isLoading ? (
        <div role="status" className="mt-3 space-y-3">
          <span className="sr-only">Loading {title.toLowerCase()}…</span>
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      ) : hasRows ? (
        <ul className="mt-1">{children}</ul>
      ) : (
        <p className="mt-3 px-2 text-sm text-faint">{empty}</p>
      )}
    </section>
  );
}

function FocusRow({ href, title, meta, children }: { href: string; title: string; meta: string; children?: ReactNode }) {
  return (
    <li>
      <Link
        href={href}
        className="flex items-center gap-3 rounded-md px-2 py-2 transition-colors hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
      >
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{title}</span>
          <span className="block truncate text-xs text-muted">{meta}</span>
        </span>
        <span className="shrink-0">{children}</span>
      </Link>
    </li>
  );
}
