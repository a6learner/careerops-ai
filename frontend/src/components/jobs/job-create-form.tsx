"use client";

import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { JOB_STATUSES, type JobStatus } from "@/lib/api/types";

export type JobInput = {
  company: string;
  title: string;
  raw_description: string;
  source_url: string | null;
  location: string | null;
  deadline: string | null;
  status: JobStatus;
};

export function JobCreateForm({
  isSubmitting,
  defaultStatus = "saved",
  onSubmit,
  onCancel,
}: {
  isSubmitting: boolean;
  defaultStatus?: JobStatus;
  onSubmit: (input: JobInput) => void;
  onCancel: () => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSubmit({
      company: String(form.get("company") ?? "").trim(),
      title: String(form.get("title") ?? "").trim(),
      raw_description: String(form.get("raw_description") ?? "").trim(),
      source_url: optionalText(form.get("source_url")),
      location: optionalText(form.get("location")),
      deadline: optionalText(form.get("deadline")),
      status: String(form.get("status") ?? "saved") as JobStatus,
    });
  }

  return (
    <form className="space-y-4" onSubmit={submit}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Company" htmlFor="job-company"><Input id="job-company" name="company" maxLength={200} required /></Field>
        <Field label="Role" htmlFor="job-title"><Input id="job-title" name="title" maxLength={200} required /></Field>
        <Field label="Location" hint="Optional" htmlFor="job-location"><Input id="job-location" name="location" maxLength={200} /></Field>
        <Field label="Deadline" hint="Optional" htmlFor="job-deadline"><Input id="job-deadline" name="deadline" type="date" /></Field>
      </div>
      <Field label="Source URL" hint="Optional" htmlFor="job-source-url"><Input id="job-source-url" name="source_url" type="url" maxLength={2_048} placeholder="https://…" /></Field>
      <Field label="Job description" htmlFor="job-description">
        <Textarea id="job-description" name="raw_description" maxLength={50_000} required rows={8} />
      </Field>
      <Field label="Starting status" htmlFor="job-status">
        <Select id="job-status" name="status" defaultValue={defaultStatus}>
          {JOB_STATUSES.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}
        </Select>
      </Field>
      <div className="flex gap-3">
        <Button disabled={isSubmitting}>{isSubmitting ? "Saving…" : "Save job"}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}


function optionalText(value: FormDataEntryValue | null): string | null {
  const text = String(value ?? "").trim();
  return text || null;
}

export function statusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}
