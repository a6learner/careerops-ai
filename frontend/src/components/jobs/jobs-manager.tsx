"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BriefcaseBusiness, CalendarClock, Columns3, MapPin, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { JobCreateForm, statusLabel, type JobInput } from "@/components/jobs/job-create-form";
import { JobDiscoveryPanel } from "@/components/jobs/job-discovery-panel";
import { daysUntil, formatDeadline, jobStatusTone } from "@/components/jobs/job-format";
import { JobStatusSelect } from "@/components/jobs/job-status-select";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { useToast } from "@/components/ui/toast";
import { apiRequest } from "@/lib/api/client";
import { JOB_STATUSES, type Job, type JobList, type JobStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const BOARD_PAGE_SIZE = 100;

export function JobsManager() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [createStatus, setCreateStatus] = useState<JobStatus | null>(null);

  const jobs = useInfiniteQuery({
    queryKey: ["jobs", "board"],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: String(BOARD_PAGE_SIZE) });
      if (pageParam) params.set("cursor", pageParam);
      return apiRequest<JobList>(`/api/v1/jobs?${params.toString()}`);
    },
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });
  const create = useMutation({
    mutationFn: (input: JobInput) =>
      apiRequest<Job>("/api/v1/jobs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(input),
      }),
    onSuccess: async (job) => {
      setCreateStatus(null);
      toast({ tone: "success", title: "Job saved", description: `${job.company} · ${job.title}` });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
  });

  const items = jobs.data?.pages.flatMap((page) => page.items) ?? [];

  function openCreate(status: JobStatus) {
    create.reset();
    setCreateStatus(status);
  }

  return (
    <div>
      <PageHeader
        icon="💼"
        title="Jobs"
        description="Target roles grouped by application status. Open a card to parse requirements and review evidence."
      />

      <JobDiscoveryPanel />

      <div className="mt-8 flex items-center justify-between gap-3 border-b pb-1.5">
        <div className="flex items-center gap-1.5 border-b-2 border-foreground pb-1.5 -mb-[8px] text-sm font-medium">
          <Columns3 className="size-4" aria-hidden="true" />
          Board
          {items.length > 0 ? <span className="font-normal text-faint">{items.length}{jobs.hasNextPage ? "+" : ""}</span> : null}
        </div>
        <Button size="sm" onClick={() => openCreate("saved")}><Plus className="size-3.5" />New</Button>
      </div>

      {createStatus ? (
        <Card className="mt-4 p-5 shadow-raised">
          <div className="mb-4 flex items-center gap-2">
            <h2 className="text-base font-semibold">New job</h2>
            <StatusBadge tone={jobStatusTone(createStatus)}>{statusLabel(createStatus)}</StatusBadge>
          </div>
          {create.error ? <div className="mb-4"><ApiFeedback error={create.error} onRetry={() => create.reset()} /></div> : null}
          <JobCreateForm key={createStatus} defaultStatus={createStatus} isSubmitting={create.isPending} onSubmit={(input) => create.mutate(input)} onCancel={() => setCreateStatus(null)} />
        </Card>
      ) : null}

      <div className="mt-4">
        {jobs.isPending ? <BoardSkeleton /> : null}
        {jobs.error ? <ApiFeedback error={jobs.error} onRetry={() => void jobs.refetch()} /> : null}
        {!jobs.isPending && !jobs.error && items.length === 0 && !createStatus ? (
          <EmptyState
            icon={BriefcaseBusiness}
            title="No jobs yet."
            description="Add a target role, or use assisted discovery above."
            action={<Button size="sm" onClick={() => openCreate("saved")}><Plus className="size-3.5" />Add job</Button>}
          />
        ) : null}
        {items.length > 0 ? <JobBoard jobs={items} onCreate={openCreate} /> : null}
      </div>

      {jobs.hasNextPage ? (
        <div className="mt-4">
          <Button variant="secondary" size="sm" disabled={jobs.isFetchingNextPage} onClick={() => void jobs.fetchNextPage()}>
            {jobs.isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function JobBoard({ jobs, onCreate }: { jobs: Job[]; onCreate: (status: JobStatus) => void }) {
  return (
    <div className="overflow-x-auto pb-4">
      <div className="flex w-max gap-3">
        {JOB_STATUSES.map((status) => {
          const column = jobs.filter((job) => job.status === status);
          return (
            <section key={status} aria-label={`${statusLabel(status)} jobs`} className="w-[260px] shrink-0">
              <div className="flex items-center gap-2 px-1 pb-2">
                <StatusBadge tone={jobStatusTone(status)} dot>{statusLabel(status)}</StatusBadge>
                <span className="text-sm text-faint">{column.length}</span>
              </div>
              <div className="space-y-2">
                {column.map((job) => <JobCard key={job.id} job={job} />)}
                <button
                  type="button"
                  onClick={() => onCreate(status)}
                  className="flex h-8 w-full items-center gap-1.5 rounded-md px-2 text-sm text-faint transition-colors hover:bg-hover hover:text-muted"
                >
                  <Plus className="size-4" aria-hidden="true" />
                  New
                </button>
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function JobCard({ job }: { job: Job }) {
  return (
    <article className="group rounded-md bg-surface shadow-card transition-colors hover:bg-[#fbfbfa]">
      <Link href={`/jobs/${job.id}`} className="block px-2.5 pt-2 pb-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 rounded-md">
        <p className="text-sm font-semibold leading-5">{job.title}</p>
        <div className="mt-1.5 flex items-center gap-1.5 text-xs text-muted">
          <CompanyMark company={job.company} />
          <span className="truncate">{job.company}</span>
        </div>
        {job.location ? (
          <p className="mt-1 flex items-center gap-1.5 text-xs text-muted"><MapPin className="size-3.5 text-faint" aria-hidden="true" /><span className="truncate">{job.location}</span></p>
        ) : null}
        {job.deadline ? <p className="mt-1 text-xs"><DeadlineLabel deadline={job.deadline} /></p> : null}
      </Link>
      <JobStatusSelect job={job} variant="inline" className="px-1.5 pb-1.5" />
    </article>
  );
}

export function CompanyMark({ company, size = "sm" }: { company: string; size?: "sm" | "lg" }) {
  const hue = [...company].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 360;
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid shrink-0 place-items-center font-semibold",
        size === "lg" ? "size-[72px] rounded-lg text-[34px]" : "size-4 rounded-[3px] text-[10px]",
      )}
      style={{ background: `hsl(${hue} 55% 92%)`, color: `hsl(${hue} 45% 32%)` }}
    >
      {company.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
}

export function DeadlineLabel({ deadline }: { deadline: string }) {
  const days = daysUntil(deadline);
  const urgent = days >= 0 && days <= 7;
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-muted", urgent && "text-[var(--tag-red-fg)]", days < 0 && "line-through")}>
      <CalendarClock className={cn("size-3.5 text-faint", urgent && "text-danger")} aria-hidden="true" />
      {formatDeadline(deadline)}
      {days >= 0 && days <= 14 ? <span className={cn(urgent && "font-medium")}>· {days === 0 ? "today" : `${days}d left`}</span> : null}
    </span>
  );
}

function BoardSkeleton() {
  return (
    <div role="status" aria-live="polite" className="flex gap-3 overflow-hidden">
      <span className="sr-only">Loading jobs…</span>
      {Array.from({ length: 4 }, (_, column) => (
        <div key={column} className="w-[260px] shrink-0 space-y-2">
          <Skeleton className="h-5 w-20" />
          {Array.from({ length: 2 }, (_, card) => (
            <div key={card} className="rounded-md p-2.5 shadow-card">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="mt-2 h-3 w-1/2" />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
