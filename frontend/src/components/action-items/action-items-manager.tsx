"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckSquare2, Columns3, LoaderCircle, Plus, X } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, type TagColor } from "@/components/ui/status-badge";
import { useToast } from "@/components/ui/toast";
import { apiRequest } from "@/lib/api/client";
import {
  ACTION_ITEM_STATUSES,
  type ActionItem,
  type ActionItemList,
  type ActionItemStatus,
  type JobList,
} from "@/lib/api/types";

const BOARD_PAGE_SIZE = 100;
const STATUS_COLORS: Record<ActionItemStatus, TagColor> = { todo: "gray", doing: "blue", done: "green" };

export function ActionItemsManager() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [showCreate, setShowCreate] = useState(false);
  const [pendingSubmission, setPendingSubmission] = useState<{ key: string; fingerprint: string } | null>(null);
  const items = useInfiniteQuery({
    queryKey: ["action-items", "board"],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: String(BOARD_PAGE_SIZE) });
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
    onSuccess: async (item) => {
      setPendingSubmission(null);
      setShowCreate(false);
      toast({ tone: "success", title: "Action item created", description: item.title });
      await invalidateActionData(queryClient);
    },
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
      <PageHeader
        icon="✅"
        title="Action Items"
        description="Turn evidence gaps into concrete preparation work and track it to done."
      />

      <div className="mt-8 flex items-center justify-between gap-3 border-b pb-1.5">
        <div className="-mb-[8px] flex items-center gap-1.5 border-b-2 border-foreground pb-1.5 text-sm font-medium">
          <Columns3 className="size-4" aria-hidden="true" />
          Board
          {allItems.length > 0 ? <span className="font-normal text-faint">{allItems.length}{items.hasNextPage ? "+" : ""}</span> : null}
        </div>
        <Button size="sm" variant={showCreate ? "secondary" : "primary"} onClick={() => setShowCreate((visible) => !visible)}>
          {showCreate ? <X className="size-3.5" aria-hidden="true" /> : <Plus className="size-3.5" aria-hidden="true" />}
          {showCreate ? "Close form" : "Add action item"}
        </Button>
      </div>

      {showCreate ? (
        <Card className="mt-4 p-5 shadow-raised">
          <form className="grid gap-4 sm:grid-cols-[minmax(180px,0.8fr)_1.2fr_auto] sm:items-end" onSubmit={submitCreate}>
            <Field label="Job" htmlFor="action-job">
              <Select id="action-job" name="job_id" required>
                <option value="">Choose a job</option>
                {jobs.data?.items.map((job) => <option key={job.id} value={job.id}>{job.company} — {job.title}</option>)}
              </Select>
            </Field>
            <Field label="Task" htmlFor="action-title">
              <Input id="action-title" name="title" maxLength={200} required placeholder="Practice explaining the caching trade-off" />
            </Field>
            <Button disabled={create.isPending || jobs.isPending}>{create.isPending ? "Creating…" : "Create"}</Button>
          </form>
          {jobs.error ? <div className="mt-4"><ApiFeedback error={jobs.error} onRetry={() => void jobs.refetch()} /></div> : null}
          {create.error ? <div className="mt-4"><ApiFeedback error={create.error} /></div> : null}
        </Card>
      ) : null}

      <div className="mt-4">
        {items.isPending ? <BoardSkeleton /> : null}
        {items.error ? <ApiFeedback error={items.error} onRetry={() => void items.refetch()} /> : null}
        {!items.isPending && !items.error && allItems.length === 0 ? (
          <EmptyState icon={CheckSquare2} title="No action items in this view." description="Create one manually or from an analysis gap on a job page." />
        ) : null}
        {allItems.length > 0 ? (
          <div className="overflow-x-auto pb-4">
            <div className="grid min-w-[720px] grid-cols-3 gap-3">
              {ACTION_ITEM_STATUSES.map((status) => {
                const column = allItems.filter((item) => item.status === status);
                return (
                  <section key={status} aria-label={`${statusLabel(status)} action items`}>
                    <div className="flex items-center gap-2 px-1 pb-2">
                      <StatusBadge tone={STATUS_COLORS[status]} dot>{statusLabel(status)}</StatusBadge>
                      <span className="text-sm text-faint">{column.length}</span>
                    </div>
                    <div className="space-y-2">
                      {column.map((item) => (
                        <ActionItemCard key={`${item.id}:${item.version}`} item={item} jobName={jobNames.get(item.job_id)} />
                      ))}
                    </div>
                  </section>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
      {items.hasNextPage ? (
        <div className="mt-2">
          <Button size="sm" variant="secondary" disabled={items.isFetchingNextPage} onClick={() => void items.fetchNextPage()}>
            {items.isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function ActionItemCard({ item, jobName }: { item: ActionItem; jobName?: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [title, setTitle] = useState(item.title);
  const [status, setStatus] = useState<ActionItemStatus>(item.status);
  const update = useMutation({
    mutationFn: () =>
      apiRequest<ActionItem>(`/api/v1/action-items/${item.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json", "if-match": String(item.version) },
        body: JSON.stringify({ title: title.trim(), status }),
      }),
    onSuccess: async (updated) => {
      toast({ tone: "success", title: updated.status === "done" ? "Marked done" : "Action item saved", description: updated.title });
      await invalidateActionData(queryClient);
    },
  });
  const changed = title.trim() !== item.title || status !== item.status;

  return (
    <article className="rounded-md bg-surface p-2.5 shadow-card">
      <label className="sr-only" htmlFor={`action-title-${item.id}`}>Action item title</label>
      <textarea
        id={`action-title-${item.id}`}
        value={title}
        maxLength={200}
        rows={1}
        onChange={(event) => setTitle(event.target.value)}
        className="w-full resize-none rounded px-1 py-0.5 [field-sizing:content] text-sm font-medium leading-5 outline-none transition-colors hover:bg-hover focus:bg-hover"
      />
      <div className="mt-1 px-1">
        {item.job_is_archived ? (
          <span className="text-xs text-muted">{jobName ?? "Archived or unavailable job"}</span>
        ) : (
          <Link href={`/jobs/${item.job_id}`} className="text-xs text-muted underline decoration-border-strong underline-offset-2 hover:text-foreground">
            {jobName ?? "Open job"}
          </Link>
        )}
      </div>
      {item.job_is_archived || item.source_evidence_match_id ? (
        <div className="mt-1.5 flex flex-wrap gap-1 px-1">
          {item.job_is_archived ? <StatusBadge tone="red">Archived job</StatusBadge> : null}
          {item.source_evidence_match_id ? <StatusBadge tone="orange">From analysis gap</StatusBadge> : null}
        </div>
      ) : null}
      <div className="mt-2 flex items-center gap-1.5">
        <label className="sr-only" htmlFor={`action-status-${item.id}`}>Status</label>
        <select
          id={`action-status-${item.id}`}
          value={status}
          onChange={(event) => setStatus(event.target.value as ActionItemStatus)}
          className="h-6 cursor-pointer rounded px-1 text-xs text-muted outline-none transition-colors hover:bg-hover focus-visible:ring-2 focus-visible:ring-brand/40"
        >
          {ACTION_ITEM_STATUSES.map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}
        </select>
        {changed ? (
          <Button size="sm" className="ml-auto h-6 px-2 text-xs" disabled={!title.trim() || update.isPending} onClick={() => update.mutate()}>
            {update.isPending ? <LoaderCircle className="size-3 animate-spin" aria-hidden="true" /> : null}
            Save
          </Button>
        ) : null}
      </div>
      {update.error ? (
        <div className="mt-2">
          <ApiFeedback error={update.error} onRetry={() => { update.reset(); void invalidateActionData(queryClient); }} />
        </div>
      ) : null}
    </article>
  );
}

function BoardSkeleton() {
  return (
    <div role="status" aria-live="polite" className="grid grid-cols-3 gap-3">
      <span className="sr-only">Loading action items…</span>
      {ACTION_ITEM_STATUSES.map((status) => (
        <div key={status} className="space-y-2">
          <Skeleton className="h-5 w-16" />
          <div className="rounded-md p-2.5 shadow-card"><Skeleton className="h-4 w-3/4" /><Skeleton className="mt-2 h-3 w-1/2" /></div>
        </div>
      ))}
    </div>
  );
}

async function invalidateActionData(queryClient: ReturnType<typeof useQueryClient>) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["action-items"] }),
    queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
  ]);
}

function statusLabel(value: ActionItemStatus): string {
  return value === "todo" ? "To do" : value.charAt(0).toUpperCase() + value.slice(1);
}
