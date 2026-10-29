"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";

import { ApiFeedback } from "@/components/api-feedback";
import { statusLabel } from "@/components/jobs/job-create-form";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { apiRequest } from "@/lib/api/client";
import { JOB_STATUSES, type Job, type JobStatus } from "@/lib/api/types";

type JobStatusSelectProps = {
  job: Job;
  variant?: "field" | "inline";
  className?: string;
};

// Each row owns its mutation so one pending update does not disable every other row.
export function JobStatusSelect({ job, variant = "field", className }: JobStatusSelectProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const update = useMutation({
    mutationFn: (status: JobStatus) =>
      apiRequest<Job>(`/api/v1/jobs/${job.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json", "if-match": String(job.version) },
        body: JSON.stringify({ status }),
      }),
    onSuccess: async (updated) => {
      toast({ tone: "success", title: `Moved to ${statusLabel(updated.status)}`, description: `${updated.company} · ${updated.title}` });
      queryClient.setQueryData(["job", job.id], updated);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
  });

  function retry() {
    update.reset();
    void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    void queryClient.invalidateQueries({ queryKey: ["job", job.id] });
  }

  const value = update.isPending && update.variables ? update.variables : job.status;
  const options = JOB_STATUSES.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>);

  return (
    <div className={className}>
      <div className="flex items-center gap-2">
        <label className="sr-only" htmlFor={`job-status-${job.id}`}>Update status</label>
        {variant === "inline" ? (
          <select
            id={`job-status-${job.id}`}
            className="h-6 max-w-full cursor-pointer rounded px-1 text-xs text-muted outline-none transition-colors hover:bg-hover focus-visible:ring-2 focus-visible:ring-brand/40 disabled:opacity-60"
            value={value}
            disabled={update.isPending}
            onChange={(event) => update.mutate(event.target.value as JobStatus)}
          >
            {options}
          </select>
        ) : (
          <Select
            id={`job-status-${job.id}`}
            className="min-w-36 flex-1"
            value={value}
            disabled={update.isPending}
            onChange={(event) => update.mutate(event.target.value as JobStatus)}
          >
            {options}
          </Select>
        )}
        {update.isPending ? <LoaderCircle className="size-3.5 animate-spin text-brand" aria-label="Saving status" /> : null}
      </div>
      {update.error ? <div className="mt-3"><ApiFeedback error={update.error} onRetry={retry} /></div> : null}
    </div>
  );
}
