"use client";

import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EXPERIENCE_KINDS, type Experience, type ExperienceKind } from "@/lib/api/types";

export type ExperienceInput = {
  title: string;
  kind: ExperienceKind;
  description: string;
  skills: string[];
  outcome: string | null;
};

type ExperienceFormProps = {
  experience?: Experience;
  isSubmitting: boolean;
  onSubmit: (input: ExperienceInput) => void;
  onCancel?: () => void;
};

export function ExperienceForm({
  experience,
  isSubmitting,
  onSubmit,
  onCancel,
}: ExperienceFormProps) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSubmit({
      title: String(form.get("title") ?? "").trim(),
      kind: String(form.get("kind") ?? "project") as ExperienceKind,
      description: String(form.get("description") ?? "").trim(),
      skills: uniqueSkills(String(form.get("skills") ?? "")),
      outcome: optionalText(form.get("outcome")),
    });
  }

  return (
    <form className="space-y-4" onSubmit={submit}>
      <div className="grid gap-4 sm:grid-cols-[1fr_180px]">
        <Field label="Title" htmlFor={`experience-title-${experience?.id ?? "new"}`}>
          <Input
            id={`experience-title-${experience?.id ?? "new"}`}
            name="title"
            defaultValue={experience?.title}
            maxLength={200}
            required
          />
        </Field>
        <Field label="Type" htmlFor={`experience-kind-${experience?.id ?? "new"}`}>
          <select
            id={`experience-kind-${experience?.id ?? "new"}`}
            name="kind"
            defaultValue={experience?.kind ?? "project"}
            className="h-11 w-full rounded-lg border bg-white px-3 text-sm outline-none focus:border-[var(--brand)] focus:ring-3 focus:ring-[var(--brand-soft)]"
          >
            {EXPERIENCE_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {titleCase(kind)}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="What you did" htmlFor={`experience-description-${experience?.id ?? "new"}`}>
        <textarea
          id={`experience-description-${experience?.id ?? "new"}`}
          name="description"
          defaultValue={experience?.description}
          maxLength={10_000}
          required
          rows={5}
          className="w-full rounded-lg border bg-white px-3 py-2.5 text-sm leading-6 outline-none focus:border-[var(--brand)] focus:ring-3 focus:ring-[var(--brand-soft)]"
        />
      </Field>
      <Field label="Skills" hint="Comma separated" htmlFor={`experience-skills-${experience?.id ?? "new"}`}>
        <Input
          id={`experience-skills-${experience?.id ?? "new"}`}
          name="skills"
          defaultValue={experience?.skills.join(", ")}
          placeholder="Python, FastAPI, PostgreSQL"
        />
      </Field>
      <Field label="Outcome" hint="Optional" htmlFor={`experience-outcome-${experience?.id ?? "new"}`}>
        <textarea
          id={`experience-outcome-${experience?.id ?? "new"}`}
          name="outcome"
          defaultValue={experience?.outcome ?? ""}
          maxLength={2_000}
          rows={2}
          className="w-full rounded-lg border bg-white px-3 py-2.5 text-sm leading-6 outline-none focus:border-[var(--brand)] focus:ring-3 focus:ring-[var(--brand-soft)]"
        />
      </Field>
      <div className="flex flex-wrap gap-3">
        <Button disabled={isSubmitting}>{isSubmitting ? "Saving…" : experience ? "Save changes" : "Add experience"}</Button>
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  );
}

function Field({
  label,
  hint,
  htmlFor,
  children,
}: {
  label: string;
  hint?: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <label className="font-medium" htmlFor={htmlFor}>{label}</label>
        {hint ? <span className="text-[var(--muted)]">{hint}</span> : null}
      </div>
      {children}
    </div>
  );
}

function uniqueSkills(value: string): string[] {
  const seen = new Set<string>();
  return value
    .split(",")
    .map((skill) => skill.trim())
    .filter((skill) => {
      const key = skill.toLocaleLowerCase();
      if (!skill || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function optionalText(value: FormDataEntryValue | null): string | null {
  const text = String(value ?? "").trim();
  return text || null;
}

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
