"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckSquare2, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api/client";
import {
  ACTION_ITEM_STATUSES,
  type ActionItem,
  type ActionItemList,
  type ActionItemStatus,
  type JobList,
} from "@/lib/api/types";

export function ActionItemsManager() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [filter, setFilter] = useState<ActionItemStatus | "all">("all");
  const [pendingSubmission, setPendingSubmission] = useState<{ key: string; fingerprint: string } | null>(null);
  const queryKey = ["action-items", filter] as const;
  const items = useInfiniteQuery({
    queryKey,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: "20" });
      if (filter !== "all") params.set("status", filter);
      if (pageParam) params.set("cursor", pageParam);
      return apiRequest<ActionItemList>(`/api/v1/action-items?${params.toString()}`);
    },
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const jobs = useQuery({
    queryKey: ["jobs", "action-item-options"],
    queryFn: () => apiRequest<JobList>("/api/v1/jobs?limit=100"),
  });
  const create = useMutation({
    mutationFn: ({ key, jobId, title }: { key: string; jobId: string; title: string }) =>
      apiRequest<ActionItem>("/api/v1/action-items", {
        method: "POST",
        headers: { "content-type": "application/json", "idempotency-key": key },
        body: JSON.stringify({ job_id: jobId, title, source_evidence_match_id: null }),
      }),
    onSuccess: async () => {
      setPendingSubmission(null);
      setShowCreate(false);
      await invalidateActionData(queryClient);
    },
  });
  const update = useMutation({
    mutationFn: ({ item, title, status }: { item: ActionItem; title: string; status: ActionItemStatus }) =>
      apiRequest<ActionItem>(`/api/v1/action-items/${item.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json", "if-match": String(item.version) },
        body: JSON.stringify({ title, status }),
      }),
    onSuccess: async () => invalidateActionData(queryClient),
  });

  const allItems = items.data?.pages.flatMap((page) => page.items) ?? [];
  const jobNames = new Map(jobs.data?.items.map((job) => [job.id, `${job.company} — ${job.title}`]));

  function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const jobId = String(form.get("job_id") ?? "");
    const title = String(form.get("title") ?? "").trim();
    const fingerprint = JSON.stringify({ jobId, title });
    const key = pendingSubmission?.fingerprint === fingerprint ? pendingSubmission.key : crypto.randomUUID();
    setPendingSubmission({ key, fingerprint });
    create.mutate({ key, jobId, title });
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-[var(--brand)]">Preparation work</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Action Items</h1>
          <p className="mt-2 text-sm text-[var(--muted)]">Turn evidence gaps into concrete work and track completion.</p>
        </div>
        <Button onClick={() => setShowCreate((visible) => !visible)}><Plus className="size-4" />{showCreate ? "Close form" : "Add action item"}</Button>
      </div>

      {showCreate ? (
        <Card className="mt-6 p-5 sm:p-6">
          <form className="grid gap-4 sm:grid-cols-[minmax(180px,0.8fr)_1.2fr_auto] sm:items-end" onSubmit={submitCreate}>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="action-job">Job</label>
              <select id="action-job" name="job_id" required className="h-11 w-full rounded-lg border bg-white px-3 text-sm outline-none focus:border-[var(--brand)]">
                <option value="">Choose a job</option>
                {jobs.data?.items.map((job) => <option key={job.id} value={job.id}>{job.company} — {job.title}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="action-title">Task</label>
              <Input id="action-title" name="title" maxLength={200} required placeholder="Practice explaining the caching trade-off" />
            </div>
            <Button disabled={create.isPending || jobs.isPending}>{create.isPending ? "Creating…" : "Create"}</Button>
          </form>
          {jobs.error ? <div className="mt-4"><ApiFeedback error={jobs.error} onRetry={() => void jobs.refetch()} /></div> : null}
          {create.error ? <div className="mt-4"><ApiFeedback error={create.error} /></div> : null}
        </Card>
      ) : null}

      <div className="mt-6 flex items-center gap-3">
        <label className="text-sm font-medium" htmlFor="action-filter">Status</label>
        <select id="action-filter" value={filter} onChange={(event) => setFilter(event.target.value as ActionItemStatus | "all")} className="h-10 rounded-lg border bg-white px-3 text-sm outline-none focus:border-[var(--brand)]">
          <option value="all">All statuses</option>
          {ACTION_ITEM_STATUSES.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}
        </select>
      </div>

      {update.error ? <div className="mt-6"><ApiFeedback error={update.error} onRetry={() => { update.reset(); void items.refetch(); }} /></div> : null}
      {items.isPending ? <Card className="mt-6 p-6 text-sm text-[var(--muted)]">Loading action items…</Card> : null}
      {items.error ? <div className="mt-6"><ApiFeedback error={items.error} onRetry={() => void items.refetch()} /></div> : null}
      {!items.isPending && !items.error && allItems.length === 0 ? (
        <Card className="mt-6 border-dashed p-8 text-center"><CheckSquare2 className="mx-auto size-7 text-slate-400" /><p className="mt-3 font-semibold">No action items in this view.</p><p className="mt-2 text-sm text-[var(--muted)]">Create one manually or from an Analysis gap.</p></Card>
      ) : null}

      <div className="mt-6 space-y-3">
        {allItems.map((item) => <ActionItemRow key={`${item.id}:${item.version}`} item={item} jobName={jobNames.get(item.job_id)} isUpdating={update.isPending} onUpdate={(title, status) => update.mutate({ item, title, status })} />)}
      </div>
      {items.hasNextPage ? <div className="mt-6 text-center"><Button variant="secondary" disabled={items.isFetchingNextPage} onClick={() => void items.fetchNextPage()}>{items.isFetchingNextPage ? "Loading…" : "Load more"}</Button></div> : null}
    </div>
  );
}

function ActionItemRow({ item, jobName, isUpdating, onUpdate }: { item: ActionItem; jobName?: string; isUpdating: boolean; onUpdate: (title: string, status: ActionItemStatus) => void }) {
  const [title, setTitle] = useState(item.title);
  const [status, setStatus] = useState<ActionItemStatus>(item.status);
  const changed = title.trim() !== item.title || status !== item.status;
  return (
    <Card className="p-4 sm:p-5">
      <div className="grid gap-4 lg:grid-cols-[1fr_160px_auto] lg:items-end">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2"><span className="text-xs font-medium text-[var(--muted)]">{jobName ?? "Archived or unavailable job"}</span>{item.job_is_archived ? <StatusBadge tone="danger">Archived job</StatusBadge> : null}{item.source_evidence_match_id ? <StatusBadge tone="brand">From analysis gap</StatusBadge> : null}</div>
          <label className="sr-only" htmlFor={`action-title-${item.id}`}>Action item title</label>
          <Input id={`action-title-${item.id}`} value={title} maxLength={200} onChange={(event) => setTitle(event.target.value)} />
        </div>
        <div className="space-y-2">
          <label className="text-xs font-medium text-[var(--muted)]" htmlFor={`action-status-${item.id}`}>Status</label>
          <select id={`action-status-${item.id}`} value={status} onChange={(event) => setStatus(event.target.value as ActionItemStatus)} className="h-11 w-full rounded-lg border bg-white px-3 text-sm outline-none focus:border-[var(--brand)]">
            {ACTION_ITEM_STATUSES.map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}
          </select>
        </div>
        <Button variant="secondary" disabled={!changed || !title.trim() || isUpdating} onClick={() => onUpdate(title.trim(), status)}>Save</Button>
      </div>
    </Card>
  );
}

async function invalidateActionData(queryClient: ReturnType<typeof useQueryClient>) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["action-items"] }),
    queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
  ]);
}

function statusLabel(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
