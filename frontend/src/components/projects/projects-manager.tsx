"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiRequest } from "@/lib/api/client";
import type {
  CheckpointPayload, CheckpointRecord, ProjectRecord, RecordPage, RecordStatus,
} from "@/lib/api/project-records";

const textAreaStyle = "min-h-24 w-full rounded-lg border bg-white px-3 py-2 text-sm focus:outline-2 focus:outline-[var(--brand)]";

export function ProjectsManager() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<ProjectRecord | null>(null);
  const pending = useRef<{ body: string; key: string } | null>(null);
  const projects = useInfiniteQuery({
    queryKey: ["projects"], initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => apiRequest<RecordPage<ProjectRecord>>(
      `/api/v1/projects?limit=20${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
    ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const create = useMutation({
    mutationFn: ({ body, key }: { body: string; key: string }) => apiRequest<ProjectRecord>(
      "/api/v1/projects", {
        method: "POST", headers: { "content-type": "application/json", "idempotency-key": key }, body,
      },
    ),
    onSuccess: async (project) => {
      pending.current = null;
      setSelected(project);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const body = JSON.stringify({ name: String(data.get("name")).trim(), goal: String(data.get("goal")).trim() });
    if (pending.current?.body !== body) pending.current = { body, key: crypto.randomUUID() };
    create.mutate(pending.current);
  }
  return <div className="space-y-6">
    <div>
      <p className="text-sm font-semibold text-[var(--brand)]">Project evidence</p>
      <h1 className="mt-1 text-3xl font-semibold">Projects</h1>
      <p className="mt-2 text-sm text-[var(--muted)]">Keep decisions, failures and source excerpts for future resume and interview preparation.</p>
    </div>
    <Card className="p-5">
      <h2 className="mb-4 text-lg font-semibold">Add a project</h2>
      <form className="grid gap-4" onSubmit={submit}>
        <label className="grid gap-2 text-sm">Project name<Input name="name" required maxLength={160} /></label>
        <label className="grid gap-2 text-sm">Project goal<Input name="goal" required maxLength={2000} /></label>
        <Button disabled={create.isPending}>{create.isPending ? "Saving…" : "Create project"}</Button>
      </form>
      {create.error ? <div className="mt-4"><ApiFeedback error={create.error} /></div> : null}
    </Card>
    {projects.isPending ? <p role="status">Loading projects…</p> : null}
    {projects.error ? <ApiFeedback error={projects.error} onRetry={() => void projects.refetch()} /> : null}
    {projects.data?.pages.flatMap((p) => p.items).length === 0 ? <p>No projects yet. Add one to start keeping evidence.</p> : null}
    <div className="flex flex-wrap gap-3" aria-label="Your projects">
      {projects.data?.pages.flatMap((p) => p.items).map((project) => <Button
        key={project.id} variant="secondary" aria-pressed={selected?.id === project.id}
        onClick={() => setSelected(project)}>{project.name}</Button>)}
    </div>
    {projects.hasNextPage ? <Button variant="secondary" disabled={projects.isFetchingNextPage}
      onClick={() => void projects.fetchNextPage()}>Load more projects</Button> : null}
    {selected ? <CheckpointWorkspace key={selected.id} project={selected} /> : <p>Select a project to review its records.</p>}
  </div>;
}

function CheckpointWorkspace({ project }: { project: ProjectRecord }) {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<RecordStatus | "all">("all");
  const [showForm, setShowForm] = useState(false);
  const records = useInfiniteQuery({
    queryKey: ["project-checkpoints", project.id, status, query],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: "20" });
      if (status !== "all") params.set("status", status);
      if (query) params.set("q", query);
      if (pageParam) params.set("cursor", pageParam);
      return apiRequest<RecordPage<CheckpointRecord>>(`/api/v1/projects/${project.id}/checkpoints?${params}`);
    },
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["project-checkpoints", project.id] });
  }
  return <section className="space-y-4" aria-label="Project records">
    <h2 className="text-2xl font-semibold">{project.name}</h2><p>{project.goal}</p>
    <p className="text-sm text-[var(--muted)]">Records are client-supplied drafts. Confirmation records your review; it does not certify authorship, skill or test execution. Withdrawn records remain in history.</p>
    <Button onClick={() => setShowForm(!showForm)}>{showForm ? "Close record form" : "Record a stage"}</Button>
    {showForm ? <CheckpointForm projectId={project.id} onSaved={async () => { setShowForm(false); await refresh(); }} /> : null}
    <form className="flex flex-wrap items-end gap-3" onSubmit={(event) => {
      event.preventDefault(); setQuery(String(new FormData(event.currentTarget).get("query") ?? "").trim());
    }}>
      <label className="grid gap-2 text-sm">Search records<Input name="query" maxLength={100} /></label>
      <label className="grid gap-2 text-sm">Record status<select className="h-11 rounded-lg border px-3"
        value={status} onChange={(e) => setStatus(e.target.value as RecordStatus | "all")}>
        <option value="all">All records</option><option value="draft">Draft</option>
        <option value="confirmed">Confirmed</option><option value="withdrawn">Withdrawn</option>
      </select></label><Button variant="secondary">Search</Button>
    </form>
    {records.isPending ? <p role="status">Loading records…</p> : null}
    {records.error ? <ApiFeedback error={records.error} onRetry={() => void records.refetch()} /> : null}
    {records.data?.pages.flatMap((p) => p.items).length === 0 ? <p>No records in this view.</p> : null}
    {records.data?.pages.flatMap((p) => p.items).map((record) => <RecordCard
      key={`${record.id}:${record.version}`} record={record} onReviewed={refresh} />)}
    {records.hasNextPage ? <Button variant="secondary" disabled={records.isFetchingNextPage}
      onClick={() => void records.fetchNextPage()}>Load more records</Button> : null}
  </section>;
}

function CheckpointForm({ projectId, onSaved }: { projectId: string; onSaved: () => Promise<void> }) {
  const pending = useRef<{ body: string; key: string } | null>(null);
  const create = useMutation({
    mutationFn: ({ body, key }: { body: string; key: string }) => apiRequest<CheckpointRecord>(
      `/api/v1/projects/${projectId}/checkpoints`, {
        method: "POST", headers: { "content-type": "application/json", "idempotency-key": key }, body,
      },
    ),
    onSuccess: async () => { pending.current = null; await onSaved(); },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const value = (name: string) => String(data.get(name) ?? "").trim();
    const payload: CheckpointPayload = {
      title: value("title"), objective: value("objective"), changes: value("changes"),
      decisions: value("decisions"), failures: value("failures"), verification: value("verification"),
      remaining: value("remaining"), contribution: value("contribution"), host: "web-manual",
      base_revision: value("base_revision") || null,
      sources: [{ kind: "user_note", locator: value("locator"), content: value("content"), quote: value("quote") }],
    };
    const body = JSON.stringify(payload);
    if (pending.current?.body !== body) pending.current = { body, key: crypto.randomUUID() };
    create.mutate(pending.current);
  }
  return <Card className="p-5"><form onSubmit={submit} className="grid gap-4">
    <h3 className="font-semibold">New stage record</h3>
    <p className="text-sm">Paste only selected non-sensitive excerpts. This form does not read or upload your repository.</p>
    <label className="grid gap-2 text-sm">Stage title<Input name="title" required maxLength={200} /></label>
    <label className="grid gap-2 text-sm">Objective<Input name="objective" required maxLength={2000} /></label>
    {([ ["changes", "What changed", 4000, true], ["decisions", "Decisions and trade-offs", 4000, false],
      ["failures", "Failures and fixes", 4000, false], ["verification", "Verification and limits", 4000, false],
      ["remaining", "Remaining work", 2000, false], ["contribution", "Proposed personal contribution", 2000, false],
    ] as const).map(([name, label, maxLength, required]) => <label key={name} className="grid gap-2 text-sm">{label}
      <textarea name={name} maxLength={maxLength} required={required} className={textAreaStyle} /></label>)}
    <label className="grid gap-2 text-sm">Base revision (optional)<Input name="base_revision" maxLength={100} /></label>
    <label className="grid gap-2 text-sm">Source label (relative, no credentials)<Input name="locator" required maxLength={300} placeholder="docs/decision-note.md" /></label>
    <label className="grid gap-2 text-sm">Source excerpt<textarea name="content" required maxLength={8000} className={textAreaStyle} /></label>
    <label className="grid gap-2 text-sm">Exact quote from the excerpt<textarea name="quote" required maxLength={2000} className={textAreaStyle} /></label>
    <Button disabled={create.isPending}>{create.isPending ? "Saving…" : "Save record draft"}</Button>
    {create.error ? <ApiFeedback error={create.error} /> : null}
  </form></Card>;
}

function RecordCard({ record, onReviewed }: { record: CheckpointRecord; onReviewed: () => Promise<void> }) {
  const [note, setNote] = useState("");
  const review = useMutation({
    mutationFn: (status: "confirmed" | "withdrawn") => apiRequest<CheckpointRecord>(
      `/api/v1/projects/${record.project_id}/checkpoints/${record.id}/review`, {
        method: "PATCH", headers: { "content-type": "application/json", "if-match": String(record.version) },
        body: JSON.stringify({ status, contribution_note: status === "confirmed" ? note.trim() : "" }),
      },
    ),
    onSuccess: onReviewed,
  });
  return <Card className="space-y-3 p-5">
    <div className="flex flex-wrap justify-between gap-2"><h3 className="font-semibold">{record.payload.title}</h3>
      <span className="text-sm">{record.status} · v{record.version}</span></div>
    <p className="whitespace-pre-wrap">{record.payload.objective}</p>
    <details><summary className="cursor-pointer text-sm font-medium">Record details and sources</summary>
      <dl className="mt-3 space-y-3 text-sm">
        {([ ["Changes", record.payload.changes], ["Decisions", record.payload.decisions],
          ["Failures", record.payload.failures], ["Verification (client supplied)", record.payload.verification],
          ["Remaining", record.payload.remaining], ["Proposed contribution", record.payload.contribution],
          ["Reviewed contribution", record.contribution_note], ["Host", record.payload.host],
          ["Base revision", record.payload.base_revision], ["Content SHA-256", record.content_sha256],
        ] as const).map(([label, value]) => value ? <div key={label}><dt className="font-medium">{label}</dt>
          <dd className="whitespace-pre-wrap break-words">{value}</dd></div> : null)}
      </dl>
      {record.payload.sources.map((source, i) => <div key={i} className="mt-4 space-y-2 border-t pt-3 text-sm">
        <p className="break-words">{source.locator} · {source.kind} · client supplied</p>
        <blockquote className="whitespace-pre-wrap border-l-2 pl-3">{source.quote}</blockquote>
        <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded bg-slate-50 p-3">{source.content}</pre>
      </div>)}
    </details>
    {record.status === "draft" ? <label className="grid gap-2 text-sm">Your actual contribution
      <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000}
        placeholder="Describe what you personally designed, implemented or verified" /></label> : null}
    <div className="flex flex-wrap gap-3">
      {record.status === "draft" ? <Button disabled={!note.trim() || review.isPending}
        onClick={() => review.mutate("confirmed")}>Confirm record</Button> : null}
      {record.status !== "withdrawn" ? <Button variant="secondary" disabled={review.isPending}
        onClick={() => review.mutate("withdrawn")}>Withdraw record</Button> : <p className="text-sm">Withdrawn: keep for history, exclude from current career claims.</p>}
    </div>
    {review.error ? <ApiFeedback error={review.error} onRetry={() => { review.reset(); void onReviewed(); }} /> : null}
  </Card>;
}
