"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { ExperienceForm, type ExperienceInput } from "@/components/experiences/experience-form";
import { CvImportPanel } from "@/components/experiences/cv-import-panel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api/client";
import type { Experience, ExperienceList } from "@/lib/api/types";

const queryKey = ["experiences"] as const;

export function ExperiencesManager() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const experiences = useQuery({
    queryKey,
    queryFn: () => apiRequest<ExperienceList>("/api/v1/experiences"),
  });
  const create = useMutation({
    mutationFn: (input: ExperienceInput) =>
      apiRequest<Experience>("/api/v1/experiences", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(input),
      }),
    onSuccess: async () => {
      setShowCreate(false);
      await queryClient.invalidateQueries({ queryKey });
    },
  });
  const update = useMutation({
    mutationFn: ({ experience, input }: { experience: Experience; input: ExperienceInput }) =>
      apiRequest<Experience>(`/api/v1/experiences/${experience.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json", "if-match": String(experience.version) },
        body: JSON.stringify(input),
      }),
    onSuccess: async () => {
      setEditingId(null);
      await queryClient.invalidateQueries({ queryKey });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiRequest<void>(`/api/v1/experiences/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      setDeletingId(null);
      await queryClient.invalidateQueries({ queryKey });
    },
  });

  const mutationError = create.error ?? update.error ?? remove.error;
  function clearMutationError() {
    create.reset();
    update.reset();
    remove.reset();
    void experiences.refetch();
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-[var(--brand)]">Evidence library</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Experiences</h1>
          <p className="mt-2 text-sm text-[var(--muted)]">Keep claims grounded in work you can explain.</p>
        </div>
        <Button onClick={() => setShowCreate((visible) => !visible)}>
          <Plus className="size-4" aria-hidden="true" />
          {showCreate ? "Close form" : "Add experience"}
        </Button>
      </div>

      {showCreate ? (
        <Card className="mt-6 p-5 sm:p-6">
          <h2 className="mb-5 text-lg font-semibold">New experience</h2>
          <ExperienceForm isSubmitting={create.isPending} onSubmit={(input) => create.mutate(input)} onCancel={() => setShowCreate(false)} />
        </Card>
      ) : null}

      <CvImportPanel />

      {mutationError ? <div className="mt-6"><ApiFeedback error={mutationError} onRetry={clearMutationError} /></div> : null}
      {experiences.isPending ? <Card className="mt-6 p-6 text-sm text-[var(--muted)]">Loading experiences…</Card> : null}
      {experiences.error ? <div className="mt-6"><ApiFeedback error={experiences.error} onRetry={() => void experiences.refetch()} /></div> : null}

      {experiences.data?.items.length === 0 ? (
        <Card className="mt-6 border-dashed p-8 text-center">
          <p className="font-semibold">Your evidence library is empty.</p>
          <p className="mt-2 text-sm text-[var(--muted)]">Add a project, role, course, or research experience to begin.</p>
        </Card>
      ) : null}

      <div className="mt-6 space-y-4">
        {experiences.data?.items.map((experience) => (
          <Card key={experience.id} className="p-5 sm:p-6">
            {editingId === experience.id ? (
              <ExperienceForm
                experience={experience}
                isSubmitting={update.isPending}
                onSubmit={(input) => update.mutate({ experience, input })}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <ExperienceView
                experience={experience}
                confirmingDelete={deletingId === experience.id}
                isDeleting={remove.isPending}
                onEdit={() => { setEditingId(experience.id); setDeletingId(null); }}
                onDelete={() => setDeletingId(experience.id)}
                onCancelDelete={() => setDeletingId(null)}
                onConfirmDelete={() => remove.mutate(experience.id)}
              />
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}

function ExperienceView({
  experience,
  confirmingDelete,
  isDeleting,
  onEdit,
  onDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  experience: Experience;
  confirmingDelete: boolean;
  isDeleting: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">{experience.title}</h2>
            <StatusBadge tone="brand">{experience.kind}</StatusBadge>
          </div>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">{experience.description}</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={onEdit}><Pencil className="size-3.5" /> Edit</Button>
          <Button size="sm" variant="ghost" onClick={onDelete}><Trash2 className="size-3.5" /> Delete</Button>
        </div>
      </div>
      {experience.skills.length ? (
        <div className="mt-4 flex flex-wrap gap-2">{experience.skills.map((skill) => <StatusBadge key={skill}>{skill}</StatusBadge>)}</div>
      ) : null}
      {experience.outcome ? <p className="mt-4 border-l-2 border-indigo-200 pl-3 text-sm text-slate-600">{experience.outcome}</p> : null}
      {confirmingDelete ? (
        <div className="mt-5 flex flex-wrap items-center gap-3 rounded-lg bg-rose-50 p-3 text-sm">
          <span className="font-medium text-rose-800">Delete this experience?</span>
          <Button size="sm" variant="danger" disabled={isDeleting} onClick={onConfirmDelete}>{isDeleting ? "Deleting…" : "Confirm delete"}</Button>
          <Button size="sm" variant="ghost" onClick={onCancelDelete}>Cancel</Button>
        </div>
      ) : null}
    </div>
  );
}
