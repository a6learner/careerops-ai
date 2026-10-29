"use client";

import { useQuery } from "@tanstack/react-query";
import { BriefcaseBusiness, CheckCircle2, ClipboardList, Send, type LucideIcon } from "lucide-react";

import { ApiFeedback } from "@/components/api-feedback";
import { Skeleton } from "@/components/ui/skeleton";
import { apiRequest } from "@/lib/api/client";
import type { DashboardSummary as DashboardSummaryData } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const PIPELINE_STAGES = [
  { key: "saved", label: "Saved", color: "bg-[#9b9a97]" },
  { key: "preparing", label: "Preparing", color: "bg-[#cb912f]" },
  { key: "applied", label: "Applied", color: "bg-[#337ea9]" },
  { key: "interview", label: "Interview", color: "bg-[#9065b0]" },
  { key: "offer", label: "Offer", color: "bg-[#448361]" },
  { key: "rejected", label: "Rejected", color: "bg-[#d44c47]" },
  { key: "withdrawn", label: "Withdrawn", color: "bg-[#a27763]" },
] as const;

export function DashboardSummary() {
  const summary = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiRequest<DashboardSummaryData>("/api/v1/dashboard/summary"),
  });

  if (summary.isPending) return <DashboardSkeleton />;
  if (summary.error) return <div className="mt-6"><ApiFeedback error={summary.error} onRetry={() => void summary.refetch()} /></div>;

  const data = summary.data;
  const openTasks = data.action_items.todo + data.action_items.doing;
  const stats: StatProps[] = [
    { label: "Tracked jobs", value: data.jobs.total, detail: `${data.jobs.saved} saved · ${data.jobs.preparing} preparing`, icon: BriefcaseBusiness },
    { label: "Submitted", value: data.jobs.applied + data.jobs.interview + data.jobs.offer, detail: `${data.jobs.interview} interviewing · ${plural(data.jobs.offer, "offer")}`, icon: Send },
    { label: "Open tasks", value: openTasks, detail: `${data.action_items.doing} in progress`, icon: ClipboardList },
    { label: "Completed tasks", value: data.action_items.done, detail: completionLabel(data.action_items.done, data.action_items.total), icon: CheckCircle2 },
  ];

  return (
    <>
      <div className="mt-8 grid grid-cols-2 gap-3 xl:grid-cols-4">
        {stats.map((stat) => <Stat key={stat.label} {...stat} />)}
      </div>
      <section className="mt-10">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b pb-2">
          <h2 className="text-lg font-semibold">Application pipeline</h2>
          <p className="text-xs text-faint">
            Updated {new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(data.generated_at))}
          </p>
        </div>
        <PipelineBar counts={data.jobs} />
      </section>
    </>
  );
}

type StatProps = { label: string; value: number; detail: string; icon: LucideIcon };

function Stat({ label, value, detail, icon: Icon }: StatProps) {
  return (
    <div className="rounded-lg bg-surface-subtle p-4">
      <p className="flex items-center gap-1.5 text-[13px] text-muted">
        <Icon className="size-3.5 text-faint" aria-hidden="true" />
        {label}
      </p>
      <p className="mt-2 text-[28px] font-semibold leading-none tabular-nums">{value}</p>
      <p className="mt-2 text-xs text-muted">{detail}</p>
    </div>
  );
}

function PipelineBar({ counts }: { counts: DashboardSummaryData["jobs"] }) {
  const total = counts.total;
  return (
    <>
      <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-surface-subtle" role="img" aria-label={pipelineDescription(counts)}>
        {total > 0
          ? PIPELINE_STAGES.map(({ key, color }) =>
              counts[key] > 0 ? (
                <div key={key} className={cn("h-full border-r-2 border-surface last:border-r-0", color)} style={{ width: `${(counts[key] / total) * 100}%` }} />
              ) : null,
            )
          : null}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4 lg:grid-cols-7">
        {PIPELINE_STAGES.map(({ key, label, color }) => (
          <div key={key} className="min-w-0">
            <dt className="flex items-center gap-1.5 text-xs text-muted">
              <span className={cn("size-2 rounded-full", color)} aria-hidden="true" />
              {label}
            </dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums">{counts[key]}</dd>
          </div>
        ))}
      </dl>
    </>
  );
}

function pipelineDescription(counts: DashboardSummaryData["jobs"]): string {
  return PIPELINE_STAGES.map(({ key, label }) => `${label} ${counts[key]}`).join(", ");
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function completionLabel(done: number, total: number): string {
  if (total === 0) return "No tasks yet";
  return `${Math.round((done / total) * 100)}% of ${total} tasks`;
}

function DashboardSkeleton() {
  return (
    <div role="status" aria-live="polite" className="mt-8">
      <span className="sr-only">Loading dashboard…</span>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index} className="rounded-lg bg-surface-subtle p-4">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-4 h-7 w-12" />
            <Skeleton className="mt-3 h-3 w-32" />
          </div>
        ))}
      </div>
      <div className="mt-10">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="mt-4 h-2 w-full" />
      </div>
    </div>
  );
}
