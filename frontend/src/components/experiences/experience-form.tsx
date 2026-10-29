"use client";

import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { EXPERIENCE_KINDS, type ExperienceKind } from "@/lib/api/types";

export type ExperienceInput = {
  title: string;
  kind: ExperienceKind;
  description: string;
  skills: string[];
  outcome: string | null;
};

type ExperienceFormProps = {
  experience?: ExperienceInput & { id: string };
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
          <Select
            id={`experience-kind-${experience?.id ?? "new"}`}
            name="kind"
            defaultValue={experience?.kind ?? "project"}
          >
            {EXPERIENCE_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {titleCase(kind)}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="What you did" htmlFor={`experience-description-${experience?.id ?? "new"}`}>
        <Textarea
          id={`experience-description-${experience?.id ?? "new"}`}
          name="description"
          defaultValue={experience?.description}
          maxLength={10_000}
          required
          rows={5}
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
        <Textarea
          id={`experience-outcome-${experience?.id ?? "new"}`}
          name="outcome"
          defaultValue={experience?.outcome ?? ""}
          maxLength={2_000}
          rows={2}
          className="min-h-16"
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
