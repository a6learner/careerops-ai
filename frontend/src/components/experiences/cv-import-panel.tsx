"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import { useState } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { ExperienceForm, type ExperienceInput } from "@/components/experiences/experience-form";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api/client";
import { describeRunError } from "@/lib/run-errors";
import { cn } from "@/lib/utils";
import type { CvImport, Experience, ExperienceDraft } from "@/lib/api/types";

export function CvImportPanel() {
  const queryClient = useQueryClient();
  const [importId, setImportId] = useState<string | null>(null);
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.set("file", file);
      return apiRequest<CvImport>("/api/v1/cv-imports", {
        method: "POST",
        headers: { "idempotency-key": crypto.randomUUID() },
        body: form,
      });
    },
    onSuccess: (record) => setImportId(record.id),
  });
  const record = useQuery({
    queryKey: ["cv-import", importId],
    queryFn: () => apiRequest<CvImport>(`/api/v1/cv-imports/${importId}`),
    enabled: importId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 1_000 : false;
    },
  });
  const update = useMutation({
    mutationFn: ({ draft, input }: { draft: ExperienceDraft; input: ExperienceInput }) =>
      apiRequest<ExperienceDraft>(`/api/v1/experience-drafts/${draft.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json", "if-match": String(draft.version) },
        body: JSON.stringify(input),
      }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["cv-import", importId] }),
  });
  const confirm = useMutation({
    mutationFn: (draftId: string) =>
      apiRequest<Experience>(`/api/v1/experience-drafts/${draftId}/confirm`, {
        method: "POST",
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["cv-import", importId] }),
        queryClient.invalidateQueries({ queryKey: ["experiences"] }),
      ]);
    },
  });
  const reject = useMutation({
    mutationFn: (draftId: string) =>
      apiRequest<void>(`/api/v1/experience-drafts/${draftId}/reject`, { method: "POST" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["cv-import", importId] }),
  });

  const error = upload.error ?? record.error ?? update.error ?? confirm.error ?? reject.error;
  return (
    <Card className="mt-8 p-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className="text-xl" aria-hidden="true">📄</span>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold">Import CV</h2>
            <p className="text-xs text-muted">
              PDF, DOCX, DOC, ODT, RTF, TXT, and Markdown. Export Google Docs as DOCX or PDF first.
            </p>
          </div>
        </div>
        <label className={cn(buttonVariants({ variant: "secondary", size: "sm" }), "cursor-pointer focus-within:ring-2 focus-within:ring-brand/40")}>
          <FileUp className="size-3.5" aria-hidden="true" />
          {upload.isPending ? "Uploading…" : "Choose CV"}
          <input
            className="sr-only"
            type="file"
            accept=".pdf,.docx,.doc,.odt,.rtf,.txt,.md,.markdown"
            disabled={upload.isPending}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload.mutate(file);
            }}
          />
        </label>
      </div>
      {error ? <div className="mt-4"><ApiFeedback error={error} /></div> : null}
      {record.data ? (
        <div className="mt-5 space-y-4">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="font-medium">{record.data.filename}</span>
            <StatusBadge tone={record.data.status === "failed" ? "red" : record.data.status === "succeeded" ? "green" : "blue"} dot>{record.data.status}</StatusBadge>
            {record.data.error_code ? <span className="text-danger">{describeRunError(record.data.error_code)} <span className="font-mono text-[11px] text-muted">({record.data.error_code})</span></span> : null}
          </div>
          {record.data.status === "succeeded" && record.data.drafts.length === 0 ? (
            <p className="text-sm text-muted">No reviewable experience blocks were found.</p>
          ) : null}
          {record.data.drafts.map((draft) => (
            <DraftEditor
              key={`${draft.id}-${draft.version}-${draft.status}`}
              draft={draft}
              isSaving={update.isPending}
              isConfirming={confirm.isPending}
              isRejecting={reject.isPending}
              onSave={(input) => update.mutate({ draft, input })}
              onConfirm={() => confirm.mutate(draft.id)}
              onReject={() => reject.mutate(draft.id)}
            />
          ))}
        </div>
      ) : null}
    </Card>
  );
}

function DraftEditor({
  draft,
  isSaving,
  isConfirming,
  isRejecting,
  onSave,
  onConfirm,
  onReject,
}: {
  draft: ExperienceDraft;
  isSaving: boolean;
  isConfirming: boolean;
  isRejecting: boolean;
  onSave: (input: ExperienceInput) => void;
  onConfirm: () => void;
  onReject: () => void;
}) {
  if (draft.status !== "pending") {
    return <div className="flex items-center gap-2 rounded-md bg-surface-subtle px-3 py-2.5 text-sm"><strong className="font-medium">{draft.title}</strong><StatusBadge tone={draft.status === "confirmed" ? "green" : "gray"}>{draft.status}</StatusBadge></div>;
  }
  return (
    <div className="rounded-md p-4 shadow-card">
      <details className="mb-4 text-sm">
        <summary className="cursor-pointer text-muted hover:text-foreground">View CV source</summary>
        <blockquote className="mt-2 whitespace-pre-wrap border-l-[3px] border-foreground pl-3.5 leading-6">
          {draft.source_refs.map((reference) => reference.quote).join("\n\n")}
        </blockquote>
      </details>
      <ExperienceForm
        experience={{
          id: draft.id,
          title: draft.title,
          kind: draft.kind,
          description: draft.description,
          skills: draft.skills,
          outcome: draft.outcome,
        }}
        isSubmitting={isSaving}
        onSubmit={onSave}
      />
      <div className="mt-3 flex flex-wrap gap-2 border-t pt-3">
        <Button size="sm" disabled={isConfirming} onClick={onConfirm}>
          {isConfirming ? "Confirming…" : "Confirm as experience"}
        </Button>
        <Button size="sm" variant="ghost" disabled={isRejecting} onClick={onReject}>
          Reject draft
        </Button>
      </div>
    </div>
  );
}
