"use client";

import { useQuery } from "@tanstack/react-query";
import { BriefcaseBusiness, CheckCircle2, ClipboardList, Send } from "lucide-react";

import { ApiFeedback } from "@/components/api-feedback";
import { Card } from "@/components/ui/card";
import { apiRequest } from "@/lib/api/client";
import type { DashboardSummary as DashboardSummaryData } from "@/lib/api/types";

export function DashboardSummary() {
  const summary = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiRequest<DashboardSummaryData>("/api/v1/dashboard/summary"),
  });

  if (summary.isPending) return <Card className="mt-8 p-6 text-sm text-[var(--muted)]">Loading dashboard…</Card>;
  if (summary.error) return <div className="mt-8"><ApiFeedback error={summary.error} onRetry={() => void summary.refetch()} /></div>;

  const data = summary.data;
  const cards = [
    { label: "Active jobs", value: data.jobs.total, detail: `${data.jobs.interview} interviewing · ${data.jobs.offer} offers`, icon: BriefcaseBusiness },
    { label: "Applications", value: data.jobs.applied, detail: `${data.jobs.preparing} preparing`, icon: Send },
    { label: "Open tasks", value: data.action_items.todo + data.action_items.doing, detail: `${data.action_items.doing} in progress`, icon: ClipboardList },
    { label: "Completed tasks", value: data.action_items.done, detail: `${data.action_items.total} total`, icon: CheckCircle2 },
  ];
  return (
    <>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(({ label, value, detail, icon: Icon }) => (
          <Card key={label} className="p-5">
            <div className="flex items-center justify-between"><p className="text-sm font-medium text-[var(--muted)]">{label}</p><Icon className="size-5 text-[var(--brand)]" /></div>
            <p className="mt-4 text-3xl font-semibold">{value}</p>
            <p className="mt-2 text-xs text-[var(--muted)]">{detail}</p>
          </Card>
        ))}
      </div>
      <Card className="mt-6 p-5">
        <p className="text-sm font-semibold">Pipeline</p>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <Count label="Saved" value={data.jobs.saved} />
          <Count label="Applied" value={data.jobs.applied} />
          <Count label="Interview" value={data.jobs.interview} />
          <Count label="Offer" value={data.jobs.offer} />
        </div>
        <p className="mt-4 text-xs text-[var(--muted)]">Updated {new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(data.generated_at))}</p>
      </Card>
    </>
  );
}

function Count({ label, value }: { label: string; value: number }) {
  return <div className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-[var(--muted)]">{label}</p><p className="mt-1 text-xl font-semibold">{value}</p></div>;
}
