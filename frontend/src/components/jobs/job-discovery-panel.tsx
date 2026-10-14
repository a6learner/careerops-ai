"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Search } from "lucide-react";
import { type FormEvent, useState } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api/client";
import type { Job, JobDiscoveryRun, JobDraft } from "@/lib/api/types";

export function JobDiscoveryPanel() {
  const queryClient = useQueryClient();
  const [runId, setRunId] = useState<string | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const search = useMutation({
    mutationFn: (input: SearchInput) =>
      apiRequest<JobDiscoveryRun>("/api/v1/job-discovery-runs", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "idempotency-key": crypto.randomUUID(),
        },
        body: JSON.stringify(input),
      }),
    onSuccess: (run) => { setRunId(run.id); setDraftId(null); },
  });
  const run = useQuery({
    queryKey: ["job-discovery", runId],
    queryFn: () => apiRequest<JobDiscoveryRun>(`/api/v1/job-discovery-runs/${runId}`),
    enabled: runId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 1_000 : false;
    },
  });
  const createDraft = useMutation({
    mutationFn: (resultId: string) =>
      apiRequest<JobDraft>(`/api/v1/job-discovery-results/${resultId}/draft`, {
        method: "POST",
      }),
    onSuccess: (draft) => setDraftId(draft.id),
  });
  const draft = useQuery({
    queryKey: ["job-draft", draftId],
    queryFn: () => apiRequest<JobDraft>(`/api/v1/job-drafts/${draftId}`),
    enabled: draftId !== null,
  });
  const updateDraft = useMutation({
    mutationFn: (input: DraftInput) => {
      if (!draft.data) throw new Error("Job draft is not loaded.");
      return apiRequest<JobDraft>(`/api/v1/job-drafts/${draft.data.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json", "if-match": String(draft.data.version) },
        body: JSON.stringify(input),
      });
    },
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["job-draft", draftId] }),
  });
  const confirm = useMutation({
    mutationFn: (id: string) => apiRequest<Job>(`/api/v1/job-drafts/${id}/confirm`, { method: "POST" }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["job-draft", draftId] }),
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      ]);
    },
  });
  const error = search.error ?? run.error ?? createDraft.error ?? draft.error ?? updateDraft.error ?? confirm.error;

  return (
    <Card className="mt-6 p-5 sm:p-6">
      <div>
        <h2 className="font-semibold">Discover public jobs</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Search runs through a worker adapter. Results are drafts until you confirm them.
        </p>
      </div>
      <SearchForm isPending={search.isPending} onSubmit={(input) => search.mutate(input)} />
      {error ? <div className="mt-4"><ApiFeedback error={error} /></div> : null}
      {run.data ? (
        <div className="mt-5 space-y-3">
          <div className="flex items-center gap-3 text-sm">
            <StatusBadge>{run.data.status}</StatusBadge>
            <span>{run.data.provider_name}</span>
            {run.data.error_code ? <span className="text-rose-700">{run.data.error_code}</span> : null}
          </div>
          {run.data.results.map((result) => (
            <div key={result.id} className="rounded-lg border p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm text-[var(--muted)]">{result.company}</p>
                  <h3 className="font-semibold">{result.title}</h3>
                </div>
                <Button size="sm" variant="secondary" onClick={() => createDraft.mutate(result.id)}>
                  Review draft
                </Button>
              </div>
              <p className="mt-2 text-sm text-slate-600">{result.summary}</p>
              <p className="mt-2 text-xs text-[var(--muted)]">
                Observed {new Date(result.observed_at).toLocaleString()}
                {result.raw_description ? " · Full description supplied" : " · Description required"}
              </p>
              <a className="mt-2 inline-flex items-center gap-1 text-xs text-[var(--brand)]" href={result.source_url} target="_blank" rel="noreferrer">
                Source <ExternalLink className="size-3" />
              </a>
            </div>
          ))}
        </div>
      ) : null}
      {draft.data ? (
        <JobDraftEditor
          key={`${draft.data.id}-${draft.data.version}`}
          draft={draft.data}
          isSaving={updateDraft.isPending}
          isConfirming={confirm.isPending}
          onSave={(input) => updateDraft.mutate(input)}
          onConfirm={() => confirm.mutate(draft.data.id)}
        />
      ) : null}
    </Card>
  );
}

type SearchInput = {
  query: string;
  location: string | null;
  remote: boolean | null;
  published_within_days: number | null;
};

function SearchForm({ isPending, onSubmit }: { isPending: boolean; onSubmit: (input: SearchInput) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const days = String(form.get("published_within_days") ?? "");
    onSubmit({
      query: String(form.get("query") ?? "").trim(),
      location: optionalText(form.get("location")),
      remote: form.get("remote") === "on" ? true : null,
      published_within_days: days ? Number(days) : null,
    });
  }
  return (
    <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={submit}>
      <label className="space-y-1 text-sm"><span className="font-medium">Keywords</span><Input name="query" required maxLength={300} placeholder="Backend Engineer" /></label>
      <label className="space-y-1 text-sm"><span className="font-medium">Location</span><Input name="location" maxLength={200} /></label>
      <label className="space-y-1 text-sm"><span className="font-medium">Published within days</span><Input name="published_within_days" type="number" min={1} max={90} /></label>
      <label className="flex items-center gap-2 self-end pb-3 text-sm"><input name="remote" type="checkbox" /> Remote roles</label>
      <div className="sm:col-span-2"><Button disabled={isPending}><Search className="size-4" />{isPending ? "Starting…" : "Search jobs"}</Button></div>
    </form>
  );
}

type DraftInput = { company: string; title: string; raw_description: string; location: string | null };

function JobDraftEditor({ draft, isSaving, isConfirming, onSave, onConfirm }: {
  draft: JobDraft;
  isSaving: boolean;
  isConfirming: boolean;
  onSave: (input: DraftInput) => void;
  onConfirm: () => void;
}) {
  if (draft.status !== "pending") {
    return (
      <div className="mt-5 rounded-lg border border-indigo-200 p-4 text-sm">
        <strong>{draft.title}</strong> — {draft.status}
      </div>
    );
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSave({
      company: String(form.get("company") ?? "").trim(),
      title: String(form.get("title") ?? "").trim(),
      raw_description: String(form.get("raw_description") ?? "").trim(),
      location: optionalText(form.get("location")),
    });
  }
  return (
    <div className="mt-5 rounded-lg border border-indigo-200 p-4">
      <h3 className="font-semibold">Review job draft</h3>
      <form className="mt-3 space-y-3" onSubmit={submit}>
        <label className="block space-y-1 text-sm"><span>Company</span><Input name="company" defaultValue={draft.company} required /></label>
        <label className="block space-y-1 text-sm"><span>Role</span><Input name="title" defaultValue={draft.title} required /></label>
        <label className="block space-y-1 text-sm"><span>Location</span><Input name="location" defaultValue={draft.location ?? ""} /></label>
        <label className="block space-y-1 text-sm"><span>Job description</span><textarea name="raw_description" defaultValue={draft.raw_description ?? ""} required rows={7} className="w-full rounded-lg border px-3 py-2 text-sm" /></label>
        {!draft.raw_description ? <p className="text-sm text-amber-700">Paste the complete job description. It will not be generated from the summary.</p> : null}
        <Button size="sm" variant="secondary" disabled={isSaving}>{isSaving ? "Saving…" : "Save draft"}</Button>
      </form>
      <div className="mt-3 border-t pt-3">
        <Button size="sm" disabled={isConfirming || !draft.raw_description} onClick={onConfirm}>
          {isConfirming ? "Confirming…" : "Confirm as job"}
        </Button>
      </div>
    </div>
  );
}

function optionalText(value: FormDataEntryValue | null): string | null {
  const text = String(value ?? "").trim();
  return text || null;
}
