"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BriefcaseBusiness, ExternalLink, Plus } from "lucide-react";
import { useState } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { JobCreateForm, statusLabel, type JobInput } from "@/components/jobs/job-create-form";
import { ParseRunPanel } from "@/components/jobs/parse-run-panel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api/client";
import { JOB_STATUSES, type Job, type JobList, type JobStatus } from "@/lib/api/types";

export function JobsManager() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [filter, setFilter] = useState<JobStatus | "all">("all");
  const queryKey = ["jobs", filter] as const;

  const jobs = useInfiniteQuery({
    queryKey,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: "20" });
      if (filter !== "all") params.set("status", filter);
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
    onSuccess: async () => {
      setShowCreate(false);
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
  const updateStatus = useMutation({
    mutationFn: ({ job, status }: { job: Job; status: JobStatus }) =>
      apiRequest<Job>(`/api/v1/jobs/${job.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json", "if-match": String(job.version) },
        body: JSON.stringify({ status }),
      }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });

  const items = jobs.data?.pages.flatMap((page) => page.items) ?? [];
  const mutationError = create.error ?? updateStatus.error;
  function clearMutationError() {
    create.reset();
    updateStatus.reset();
    void jobs.refetch();
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-[var(--brand)]">Application pipeline</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Jobs</h1>
          <p className="mt-2 text-sm text-[var(--muted)]">Save target roles and keep their application state current.</p>
        </div>
        <Button onClick={() => setShowCreate((visible) => !visible)}><Plus className="size-4" />{showCreate ? "Close form" : "Add job"}</Button>
      </div>

      {showCreate ? (
        <Card className="mt-6 p-5 sm:p-6">
          <h2 className="mb-5 text-lg font-semibold">New job</h2>
          <JobCreateForm isSubmitting={create.isPending} onSubmit={(input) => create.mutate(input)} onCancel={() => setShowCreate(false)} />
        </Card>
      ) : null}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <label className="text-sm font-medium" htmlFor="job-filter">Status</label>
        <select id="job-filter" value={filter} onChange={(event) => setFilter(event.target.value as JobStatus | "all")} className="h-10 rounded-lg border bg-white px-3 text-sm outline-none focus:border-[var(--brand)]">
          <option value="all">All statuses</option>
          {JOB_STATUSES.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}
        </select>
      </div>

      {mutationError ? <div className="mt-6"><ApiFeedback error={mutationError} onRetry={clearMutationError} /></div> : null}
      {jobs.isPending ? <Card className="mt-6 p-6 text-sm text-[var(--muted)]">Loading jobs…</Card> : null}
      {jobs.error ? <div className="mt-6"><ApiFeedback error={jobs.error} onRetry={() => void jobs.refetch()} /></div> : null}

      {!jobs.isPending && !jobs.error && items.length === 0 ? (
        <Card className="mt-6 border-dashed p-8 text-center">
          <BriefcaseBusiness className="mx-auto size-7 text-slate-400" aria-hidden="true" />
          <p className="mt-3 font-semibold">No jobs in this view.</p>
          <p className="mt-2 text-sm text-[var(--muted)]">Add a target role or choose another status.</p>
        </Card>
      ) : null}

      <div className="mt-6 grid gap-4 xl:grid-cols-2">
        {items.map((job) => <JobCard key={job.id} job={job} isUpdating={updateStatus.isPending} onUpdate={(status) => updateStatus.mutate({ job, status })} />)}
      </div>

      {jobs.hasNextPage ? (
        <div className="mt-6 text-center"><Button variant="secondary" disabled={jobs.isFetchingNextPage} onClick={() => void jobs.fetchNextPage()}>{jobs.isFetchingNextPage ? "Loading…" : "Load more"}</Button></div>
      ) : null}
    </div>
  );
}

function JobCard({ job, isUpdating, onUpdate }: { job: Job; isUpdating: boolean; onUpdate: (status: JobStatus) => void }) {
  const sourceUrl = safeExternalUrl(job.source_url);
  return (
    <Card className="flex flex-col p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div><p className="text-sm font-medium text-[var(--muted)]">{job.company}</p><h2 className="mt-1 text-lg font-semibold">{job.title}</h2></div>
        <StatusBadge tone={statusTone(job.status)}>{statusLabel(job.status)}</StatusBadge>
      </div>
      <p className="mt-4 line-clamp-3 text-sm leading-6 text-slate-600">{job.raw_description}</p>
      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs text-[var(--muted)]">
        {job.location ? <span>{job.location}</span> : null}
        {job.deadline ? <span>Deadline {formatDate(job.deadline)}</span> : null}
        {sourceUrl ? <a className="inline-flex items-center gap-1 text-[var(--brand)] hover:underline" href={sourceUrl} target="_blank" rel="noreferrer">Source <ExternalLink className="size-3" /></a> : null}
      </div>
      <JobStatusControl key={job.version} job={job} isUpdating={isUpdating} onUpdate={onUpdate} />
      <ParseRunPanel job={job} />
    </Card>
  );
}

function JobStatusControl({ job, isUpdating, onUpdate }: { job: Job; isUpdating: boolean; onUpdate: (status: JobStatus) => void }) {
  const [nextStatus, setNextStatus] = useState<JobStatus>(job.status);
  return (
    <div className="mt-5 flex flex-wrap items-end gap-3 border-t pt-4">
        <div className="min-w-40 flex-1 space-y-1.5">
          <label className="text-xs font-medium text-[var(--muted)]" htmlFor={`job-status-${job.id}`}>Update status</label>
          <select id={`job-status-${job.id}`} value={nextStatus} onChange={(event) => setNextStatus(event.target.value as JobStatus)} className="h-10 w-full rounded-lg border bg-white px-3 text-sm outline-none focus:border-[var(--brand)]">
            {JOB_STATUSES.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}
          </select>
        </div>
        <Button size="sm" variant="secondary" disabled={isUpdating || nextStatus === job.status} onClick={() => onUpdate(nextStatus)}>Update</Button>
    </div>
  );
}

function statusTone(status: JobStatus): "neutral" | "brand" | "success" | "danger" {
  if (status === "offer") return "success";
  if (status === "rejected" || status === "withdrawn") return "danger";
  if (status === "applied" || status === "interview") return "brand";
  return "neutral";
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}

function safeExternalUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}
