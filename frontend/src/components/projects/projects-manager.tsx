"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, FileText, Plus, Search, X } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, type TagColor } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { apiRequest } from "@/lib/api/client";
import type {
  CheckpointPayload, CheckpointRecord, ProjectRecord, RecordPage, RecordStatus,
} from "@/lib/api/project-records";
import { cn } from "@/lib/utils";

const RECORD_STATUS_COLORS: Record<RecordStatus, TagColor> = { draft: "yellow", confirmed: "green", withdrawn: "gray" };

export function ProjectsManager() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [selected, setSelected] = useState<ProjectRecord | null>(null);
  const [showCreate, setShowCreate] = useState(false);
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
      setShowCreate(false);
      toast({ tone: "success", title: "Project created", description: project.name });
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

  const items = projects.data?.pages.flatMap((page) => page.items) ?? [];
  const noProjects = !projects.isPending && !projects.error && items.length === 0;
  const formVisible = showCreate || noProjects;
  const active = selected ?? items[0] ?? null;

  return (
    <div>
      <PageHeader
        icon="🗂️"
        title="Projects"
        description="Keep decisions, failures and source excerpts while the work is fresh, for later resume and interview preparation."
      />

      <div className="mt-8 grid gap-8 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside aria-label="Your projects" className="lg:sticky lg:top-16 lg:self-start">
          <div className="flex items-center justify-between px-2 pb-1.5">
            <p className="text-xs font-medium text-faint">Projects</p>
            {!noProjects ? (
              <button
                type="button"
                className="rounded p-0.5 text-faint transition-colors hover:bg-hover hover:text-foreground"
                aria-label={showCreate ? "Close project form" : "New project"}
                onClick={() => setShowCreate((value) => !value)}
              >
                {showCreate ? <X className="size-4" aria-hidden="true" /> : <Plus className="size-4" aria-hidden="true" />}
              </button>
            ) : null}
          </div>
          {projects.isPending ? (
            <div role="status" className="space-y-2 px-2"><span className="sr-only">Loading projects…</span><Skeleton className="h-4 w-32" /><Skeleton className="h-4 w-24" /></div>
          ) : null}
          {projects.error ? <ApiFeedback error={projects.error} onRetry={() => void projects.refetch()} /> : null}
          <ul className="space-y-px">
            {items.map((project) => (
              <li key={project.id}>
                <button
                  type="button"
                  aria-pressed={active?.id === project.id}
                  onClick={() => setSelected(project)}
                  className={cn(
                    "flex h-[30px] w-full items-center gap-2 rounded-md px-2 text-left text-sm transition-colors",
                    active?.id === project.id ? "bg-hover font-medium" : "text-muted hover:bg-hover hover:text-foreground",
                  )}
                >
                  <FileText className="size-4 shrink-0 text-faint" strokeWidth={1.75} aria-hidden="true" />
                  <span className="truncate">{project.name}</span>
                </button>
              </li>
            ))}
          </ul>
          {projects.hasNextPage ? (
            <Button size="sm" variant="ghost" className="mt-1" disabled={projects.isFetchingNextPage} onClick={() => void projects.fetchNextPage()}>
              Load more projects
            </Button>
          ) : null}
        </aside>

        <div className="min-w-0">
          {formVisible ? (
            <Card className="mb-8 p-5 shadow-raised">
              <h2 className="mb-4 text-base font-semibold">Add a project</h2>
              <form className="grid gap-4" onSubmit={submit}>
                <Field label="Project name" htmlFor="project-name"><Input id="project-name" name="name" required maxLength={160} /></Field>
                <Field label="Project goal" htmlFor="project-goal"><Input id="project-goal" name="goal" required maxLength={2000} /></Field>
                <div><Button disabled={create.isPending}>{create.isPending ? "Saving…" : "Create project"}</Button></div>
              </form>
              {create.error ? <div className="mt-4"><ApiFeedback error={create.error} /></div> : null}
            </Card>
          ) : null}
          {active ? <CheckpointWorkspace key={active.id} project={active} /> : null}
        </div>
      </div>
    </div>
  );
}

function CheckpointWorkspace({ project }: { project: ProjectRecord }) {
  const queryClient = useQueryClient();
  const toast = useToast();
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
  const items = records.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <section aria-label="Project records">
      <h2 className="text-[28px] font-bold leading-tight tracking-tight">{project.name}</h2>
      <p className="mt-1.5 text-[15px] leading-6 text-muted">{project.goal}</p>
      <Callout icon="ℹ️" className="mt-4 text-muted">
        Records are client-supplied drafts. Confirmation records your review; it does not certify authorship, skill or test execution. Withdrawn records remain in history.
      </Callout>

      <div className="mt-6 flex flex-wrap items-end justify-between gap-3 border-b pb-3">
        <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => {
          event.preventDefault(); setQuery(String(new FormData(event.currentTarget).get("query") ?? "").trim());
        }}>
          <Field label="Search records" htmlFor={`record-query-${project.id}`}>
            <Input id={`record-query-${project.id}`} name="query" maxLength={100} className="w-44" />
          </Field>
          <Field label="Record status" htmlFor={`record-status-${project.id}`}>
            <Select id={`record-status-${project.id}`} value={status} onChange={(e) => setStatus(e.target.value as RecordStatus | "all")}>
              <option value="all">All records</option><option value="draft">Draft</option>
              <option value="confirmed">Confirmed</option><option value="withdrawn">Withdrawn</option>
            </Select>
          </Field>
          <Button variant="secondary"><Search className="size-3.5" aria-hidden="true" />Search</Button>
        </form>
        <Button onClick={() => setShowForm(!showForm)}>{showForm ? "Close record form" : "Record a stage"}</Button>
      </div>

      {showForm ? (
        <CheckpointForm
          projectId={project.id}
          onSaved={async () => {
            setShowForm(false);
            toast({ tone: "success", title: "Record draft saved", description: "Review its sources, then confirm your contribution." });
            await refresh();
          }}
        />
      ) : null}

      <div className="mt-4 space-y-3">
        {records.isPending ? <div role="status" className="space-y-2"><span className="sr-only">Loading records…</span><Skeleton className="h-16 w-full" /></div> : null}
        {records.error ? <ApiFeedback error={records.error} onRetry={() => void records.refetch()} /> : null}
        {!records.isPending && !records.error && items.length === 0 ? <p className="px-1 text-sm text-faint">No records in this view.</p> : null}
        {items.map((record) => <RecordCard key={`${record.id}:${record.version}`} record={record} onReviewed={refresh} />)}
        {records.hasNextPage ? <Button variant="secondary" size="sm" disabled={records.isFetchingNextPage}
          onClick={() => void records.fetchNextPage()}>Load more records</Button> : null}
      </div>
    </section>
  );
}

const PAYLOAD_TEXT_FIELDS = [
  ["changes", "What changed", 4000, true], ["decisions", "Decisions and trade-offs", 4000, false],
  ["failures", "Failures and fixes", 4000, false], ["verification", "Verification and limits", 4000, false],
  ["remaining", "Remaining work", 2000, false], ["contribution", "Proposed personal contribution", 2000, false],
] as const;

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
  const id = (name: string) => `checkpoint-${projectId}-${name}`;
  return (
    <Card className="mt-4 p-5 shadow-raised">
      <form onSubmit={submit} className="grid gap-4">
        <div>
          <h3 className="text-base font-semibold">New stage record</h3>
          <p className="mt-1 text-sm text-muted">Paste only selected non-sensitive excerpts. This form does not read or upload your repository.</p>
        </div>
        <Field label="Stage title" htmlFor={id("title")}><Input id={id("title")} name="title" required maxLength={200} /></Field>
        <Field label="Objective" htmlFor={id("objective")}><Input id={id("objective")} name="objective" required maxLength={2000} /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          {PAYLOAD_TEXT_FIELDS.map(([name, label, maxLength, required]) => (
            <Field key={name} label={label} htmlFor={id(name)}>
              <Textarea id={id(name)} name={name} maxLength={maxLength} required={required} />
            </Field>
          ))}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Base revision (optional)" htmlFor={id("base_revision")}><Input id={id("base_revision")} name="base_revision" maxLength={100} /></Field>
          <Field label="Source label (relative, no credentials)" htmlFor={id("locator")}><Input id={id("locator")} name="locator" required maxLength={300} placeholder="docs/decision-note.md" /></Field>
        </div>
        <Field label="Source excerpt" htmlFor={id("content")}><Textarea id={id("content")} name="content" required maxLength={8000} className="font-mono text-[13px]" /></Field>
        <Field label="Exact quote from the excerpt" htmlFor={id("quote")}><Textarea id={id("quote")} name="quote" required maxLength={2000} className="min-h-16" /></Field>
        <div><Button disabled={create.isPending}>{create.isPending ? "Saving…" : "Save record draft"}</Button></div>
        {create.error ? <ApiFeedback error={create.error} /> : null}
      </form>
    </Card>
  );
}

function RecordCard({ record, onReviewed }: { record: CheckpointRecord; onReviewed: () => Promise<void> }) {
  const toast = useToast();
  const [note, setNote] = useState("");
  const [confirmingWithdraw, setConfirmingWithdraw] = useState(false);
  const review = useMutation({
    mutationFn: (status: "confirmed" | "withdrawn") => apiRequest<CheckpointRecord>(
      `/api/v1/projects/${record.project_id}/checkpoints/${record.id}/review`, {
        method: "PATCH", headers: { "content-type": "application/json", "if-match": String(record.version) },
        body: JSON.stringify({ status, contribution_note: status === "confirmed" ? note.trim() : "" }),
      },
    ),
    onSuccess: async (updated) => {
      toast({ tone: "success", title: updated.status === "confirmed" ? "Record confirmed" : "Record withdrawn", description: updated.payload.title });
      await onReviewed();
    },
  });
  const details = ([
    ["Changes", record.payload.changes], ["Decisions", record.payload.decisions],
    ["Failures", record.payload.failures], ["Verification (client supplied)", record.payload.verification],
    ["Remaining", record.payload.remaining], ["Proposed contribution", record.payload.contribution],
    ["Reviewed contribution", record.contribution_note],
  ] as const).filter(([, value]) => Boolean(value));

  return (
    <article className="rounded-md bg-surface p-4 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-[15px] font-semibold">{record.payload.title}</h3>
        <span className="flex items-center gap-1.5">
          <StatusBadge tone={RECORD_STATUS_COLORS[record.status]} dot>{record.status}</StatusBadge>
          <span className="text-xs text-faint">v{record.version}</span>
        </span>
      </div>
      <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-muted">{record.payload.objective}</p>

      <details className="group mt-2">
        <summary className="-ml-1 flex w-fit cursor-pointer list-none items-center gap-1 rounded px-1 py-0.5 text-sm text-muted transition-colors hover:bg-hover hover:text-foreground [&::-webkit-details-marker]:hidden">
          <ChevronRight className="size-4 transition-transform group-open:rotate-90" aria-hidden="true" />
          Record details and sources
        </summary>
        <dl className="mt-3 space-y-3 pl-5 text-sm">
          {details.map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs font-medium text-muted">{label}</dt>
              <dd className="mt-0.5 whitespace-pre-wrap break-words leading-6">{value}</dd>
            </div>
          ))}
        </dl>
        {record.payload.sources.map((source, index) => (
          <div key={index} className="mt-4 space-y-2 pl-5 text-sm">
            <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
              <code className="rounded bg-[rgb(135_131_120/0.15)] px-1.5 py-0.5 font-mono text-[#eb5757]">{source.locator}</code>
              <span>{source.kind} · client supplied</span>
            </p>
            <blockquote className="whitespace-pre-wrap border-l-[3px] border-foreground pl-3.5 leading-6">{source.quote}</blockquote>
            <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-surface-subtle p-3 font-mono text-[13px] leading-6">{source.content}</pre>
          </div>
        ))}
        <dl className="mt-4 grid gap-x-4 gap-y-1 pl-5 text-xs text-faint sm:grid-cols-[auto_1fr]">
          <dt>Host</dt><dd className="break-all">{record.payload.host}</dd>
          {record.payload.base_revision ? <><dt>Base revision</dt><dd className="break-all font-mono">{record.payload.base_revision}</dd></> : null}
          <dt>Content SHA-256</dt><dd className="break-all font-mono" title={record.content_sha256}>{record.content_sha256}</dd>
        </dl>
      </details>

      {record.status === "draft" ? (
        <div className="mt-3">
          <Field label="Your actual contribution" htmlFor={`record-note-${record.id}`}>
            <Input id={`record-note-${record.id}`} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000}
              placeholder="Describe what you personally designed, implemented or verified" />
          </Field>
        </div>
      ) : null}

      {confirmingWithdraw ? (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md bg-danger-soft px-3 py-2.5 text-sm">
          <span className="mr-auto text-[var(--tag-red-fg)]">Withdraw this record? It stays in history but is excluded from current career claims.</span>
          <Button size="sm" variant="ghost" onClick={() => setConfirmingWithdraw(false)}>Cancel</Button>
          <Button size="sm" variant="danger" disabled={review.isPending} onClick={() => review.mutate("withdrawn")}>
            {review.isPending ? "Withdrawing…" : "Confirm withdraw"}
          </Button>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          {record.status === "draft" ? <Button size="sm" disabled={!note.trim() || review.isPending}
            onClick={() => review.mutate("confirmed")}>Confirm record</Button> : null}
          {record.status !== "withdrawn" ? <Button size="sm" variant="secondary" disabled={review.isPending}
            onClick={() => setConfirmingWithdraw(true)}>Withdraw record</Button> : <p className="text-sm text-muted">Withdrawn: keep for history, exclude from current career claims.</p>}
        </div>
      )}
      {review.error ? <div className="mt-3"><ApiFeedback error={review.error} onRetry={() => { review.reset(); void onReviewed(); }} /></div> : null}
    </article>
  );
}
