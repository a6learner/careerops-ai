"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LayoutGrid, Library, Pencil, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { ExperienceForm, type ExperienceInput } from "@/components/experiences/experience-form";
import { CvImportPanel } from "@/components/experiences/cv-import-panel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, type TagColor } from "@/components/ui/status-badge";
import { useToast } from "@/components/ui/toast";
import { apiRequest } from "@/lib/api/client";
import type { Experience, ExperienceKind, ExperienceList } from "@/lib/api/types";

const queryKey = ["experiences"] as const;
const MAX_VISIBLE_SKILLS = 6;

const KIND_COLORS: Record<ExperienceKind, TagColor> = {
  project: "blue",
  work: "green",
  research: "purple",
  course: "yellow",
  other: "gray",
};

export function ExperiencesManager() {
  const queryClient = useQueryClient();
  const toast = useToast();
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
    onSuccess: async (experience) => {
      setShowCreate(false);
      toast({ tone: "success", title: "Experience added", description: experience.title });
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
    onSuccess: async (experience) => {
      setEditingId(null);
      toast({ tone: "success", title: "Changes saved", description: `${experience.title} · v${experience.version}` });
      await queryClient.invalidateQueries({ queryKey });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiRequest<void>(`/api/v1/experiences/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      setDeletingId(null);
      toast({ tone: "success", title: "Experience deleted" });
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

  const items = experiences.data?.items ?? [];

  return (
    <div>
      <PageHeader
        icon="📚"
        title="Experiences"
        description="Your evidence library. Analysis can only cite text that exists here, so keep claims grounded in work you can explain."
      />

      <CvImportPanel />

      <div className="mt-8 flex items-center justify-between gap-3 border-b pb-1.5">
        <div className="-mb-[8px] flex items-center gap-1.5 border-b-2 border-foreground pb-1.5 text-sm font-medium">
          <LayoutGrid className="size-4" aria-hidden="true" />
          Gallery
          {items.length > 0 ? <span className="font-normal text-faint">{items.length}</span> : null}
        </div>
        <Button size="sm" variant={showCreate ? "secondary" : "primary"} onClick={() => setShowCreate((visible) => !visible)}>
          {showCreate ? <X className="size-3.5" aria-hidden="true" /> : <Plus className="size-3.5" aria-hidden="true" />}
          {showCreate ? "Close form" : "Add experience"}
        </Button>
      </div>

      {showCreate ? (
        <Card className="mt-4 p-5 shadow-raised">
          <h2 className="mb-4 text-base font-semibold">New experience</h2>
          <ExperienceForm isSubmitting={create.isPending} onSubmit={(input) => create.mutate(input)} onCancel={() => setShowCreate(false)} />
        </Card>
      ) : null}

      {mutationError ? <div className="mt-4"><ApiFeedback error={mutationError} onRetry={clearMutationError} /></div> : null}
      {experiences.error ? <div className="mt-4"><ApiFeedback error={experiences.error} onRetry={() => void experiences.refetch()} /></div> : null}

      {experiences.isPending ? <GallerySkeleton /> : null}

      {experiences.data?.items.length === 0 ? (
        <EmptyState
          className="mt-4"
          icon={Library}
          title="Your evidence library is empty."
          description="Add a project, role, course or research experience, or import a CV above."
        />
      ) : null}

      {items.length > 0 ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((experience) =>
            editingId === experience.id ? (
              <Card key={experience.id} className="p-5 shadow-raised sm:col-span-2 xl:col-span-3">
                <ExperienceForm
                  experience={experience}
                  isSubmitting={update.isPending}
                  onSubmit={(input) => update.mutate({ experience, input })}
                  onCancel={() => setEditingId(null)}
                />
              </Card>
            ) : (
              <ExperienceCard
                key={experience.id}
                experience={experience}
                confirmingDelete={deletingId === experience.id}
                isDeleting={remove.isPending && remove.variables === experience.id}
                onEdit={() => { setEditingId(experience.id); setDeletingId(null); }}
                onDelete={() => setDeletingId(experience.id)}
                onCancelDelete={() => setDeletingId(null)}
                onConfirmDelete={() => remove.mutate(experience.id)}
              />
            ),
          )}
        </div>
      ) : null}
    </div>
  );
}

type ExperienceCardProps = {
  experience: Experience;
  confirmingDelete: boolean;
  isDeleting: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
};

function ExperienceCard({
  experience,
  confirmingDelete,
  isDeleting,
  onEdit,
  onDelete,
  onCancelDelete,
  onConfirmDelete,
}: ExperienceCardProps) {
  const hiddenSkills = experience.skills.length - MAX_VISIBLE_SKILLS;
  return (
    <article
      id={`experience-${experience.id}`}
      className="group flex scroll-mt-20 flex-col rounded-md bg-surface shadow-card transition-shadow target:ring-2 target:ring-brand/50"
    >
      <div className="flex-1 p-3.5">
        <div className="flex items-start justify-between gap-2">
          <StatusBadge tone={KIND_COLORS[experience.kind]}>{experience.kind}</StatusBadge>
          <span className="text-xs text-faint">v{experience.version}</span>
        </div>
        <h2 className="mt-2 text-[15px] font-semibold leading-snug">{experience.title}</h2>
        <p className="mt-1.5 line-clamp-4 whitespace-pre-wrap text-sm leading-6 text-muted">{experience.description}</p>
        {experience.outcome ? (
          <p className="mt-2 border-l-[3px] border-foreground/80 pl-2.5 text-[13px] leading-5">{experience.outcome}</p>
        ) : null}
        {experience.skills.length ? (
          <div className="mt-3 flex flex-wrap gap-1">
            {experience.skills.slice(0, MAX_VISIBLE_SKILLS).map((skill) => <StatusBadge key={skill}>{skill}</StatusBadge>)}
            {hiddenSkills > 0 ? <span className="px-1 text-xs leading-5 text-faint">+{hiddenSkills}</span> : null}
          </div>
        ) : null}
      </div>
      {confirmingDelete ? (
        <div className="flex flex-wrap items-center gap-2 border-t bg-danger-soft px-3.5 py-2.5 text-sm">
          <span className="mr-auto font-medium text-[var(--tag-red-fg)]">Delete this experience?</span>
          <Button size="sm" variant="ghost" onClick={onCancelDelete}>Cancel</Button>
          <Button size="sm" variant="danger" disabled={isDeleting} onClick={onConfirmDelete}>{isDeleting ? "Deleting…" : "Confirm delete"}</Button>
        </div>
      ) : (
        <div className="flex gap-1 border-t px-2 py-1.5">
          <Button size="sm" variant="ghost" onClick={onEdit}><Pencil className="size-3.5" aria-hidden="true" />Edit</Button>
          <Button size="sm" variant="ghost" onClick={onDelete}><Trash2 className="size-3.5" aria-hidden="true" />Delete</Button>
        </div>
      )}
    </article>
  );
}

function GallerySkeleton() {
  return (
    <div role="status" aria-live="polite" className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <span className="sr-only">Loading experiences…</span>
      {Array.from({ length: 3 }, (_, index) => (
        <div key={index} className="rounded-md p-3.5 shadow-card">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="mt-3 h-4 w-3/4" />
          <Skeleton className="mt-3 h-3 w-full" />
          <Skeleton className="mt-2 h-3 w-5/6" />
        </div>
      ))}
    </div>
  );
}
