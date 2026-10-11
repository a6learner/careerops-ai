"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, LoaderCircle, Play } from "lucide-react";
import { useState } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { AnalysisRunPanel } from "@/components/jobs/analysis-run-panel";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiRequestError, apiRequest } from "@/lib/api/client";
import type { Job, JobRequirement, ParseRun, ParseRunStatus } from "@/lib/api/types";

const TERMINAL_STATUSES = new Set<ParseRunStatus>(["succeeded", "failed", "cancelled"]);

export function ParseRunPanel({ job }: { job: Job }) {
  const [isOpen, setIsOpen] = useState(false);
  const [submittedRun, setSubmittedRun] = useState<ParseRun | null>(null);
  const [pendingKey, setPendingKey] = useState<string | null>(null);

  const runQuery = useQuery({
    queryKey: ["parse-run", job.id, submittedRun?.id],
    queryFn: () =>
      apiRequest<ParseRun>(`/api/v1/jobs/${job.id}/parse-runs/${submittedRun?.id}`),
    enabled: submittedRun !== null,
    refetchInterval: (query) => {
      const run = query.state.data;
      return run && TERMINAL_STATUSES.has(run.status) ? false : 1_500;
    },
  });
  const submit = useMutation({
    mutationFn: (idempotencyKey: string) =>
      apiRequest<ParseRun>(`/api/v1/jobs/${job.id}/parse-runs`, {
        method: "POST",
        headers: { "idempotency-key": idempotencyKey },
      }),
    onSuccess: (run) => {
      setPendingKey(null);
      setSubmittedRun(run);
    },
  });

  const currentRun = runQuery.data ?? submittedRun;

  function submitWithKey(idempotencyKey: string) {
    setIsOpen(true);
    setPendingKey(idempotencyKey);
    submit.mutate(idempotencyKey);
  }

  function startOrRetry() {
    submitWithKey(pendingKey ?? crypto.randomUUID());
  }

  function startNewRun() {
    setSubmittedRun(null);
    submit.reset();
    submitWithKey(crypto.randomUUID());
  }

  const submitConflict = submit.error instanceof ApiRequestError && submit.error.status === 409;

  return (
    <div className="mt-5 border-t pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">Structured requirements</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Parse this job description through the existing worker workflow.
          </p>
        </div>
        {currentRun ? (
          <Button variant="ghost" size="sm" onClick={() => setIsOpen((open) => !open)}>
            {isOpen ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            {isOpen ? "Hide" : "View"}
          </Button>
        ) : (
          <Button variant="secondary" size="sm" disabled={submit.isPending} onClick={startOrRetry}>
            {submit.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Play className="size-4" />}
            {submit.isPending ? "Submitting…" : "Parse description"}
          </Button>
        )}
      </div>

      {isOpen ? (
        <div className="mt-4 space-y-4">
          {submit.error ? (
            <ApiFeedback error={submit.error} onRetry={submitConflict ? startNewRun : startOrRetry} />
          ) : null}
          {runQuery.error ? <ApiFeedback error={runQuery.error} onRetry={() => void runQuery.refetch()} /> : null}
          {currentRun ? (
            <RunResult job={job} run={currentRun} isRefreshing={runQuery.isFetching} onStartNew={startNewRun} />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function RunResult({ job, run, isRefreshing, onStartNew }: { job: Job; run: ParseRun; isRefreshing: boolean; onStartNew: () => void }) {
  const isActive = run.status === "queued" || run.status === "running";
  return (
    <div className="rounded-lg bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <StatusBadge tone={parseStatusTone(run.status)}>{statusLabel(run.status)}</StatusBadge>
          {isActive && isRefreshing ? <LoaderCircle aria-label="Checking parse status" className="size-4 animate-spin text-[var(--brand)]" /> : null}
          <span className="text-xs text-[var(--muted)]">Attempt {run.attempt}</span>
        </div>
        {TERMINAL_STATUSES.has(run.status) ? <Button size="sm" variant="ghost" onClick={onStartNew}>Parse again</Button> : null}
      </div>

      {isActive ? <p className="mt-3 text-sm text-slate-600">The worker will update this view automatically.</p> : null}
      {run.status === "failed" ? (
        <div className="mt-3 rounded-md bg-rose-50 p-3 text-sm text-rose-800">
          Parsing failed with code <span className="font-mono font-semibold">{run.error_code ?? "UNKNOWN"}</span>. No requirements were saved.
        </div>
      ) : null}
      {run.status === "cancelled" ? <p className="mt-3 text-sm text-slate-600">This parse run was cancelled before completion.</p> : null}
      {run.status === "succeeded" ? (
        <>
          <Requirements requirements={run.requirements} />
          <AnalysisRunPanel job={job} parseRun={run} />
        </>
      ) : null}
    </div>
  );
}

function Requirements({ requirements }: { requirements: JobRequirement[] }) {
  if (requirements.length === 0) {
    return <p className="mt-3 text-sm text-slate-600">Parsing succeeded, but no requirements were found.</p>;
  }

  return (
    <div className="mt-4 space-y-3">
      {requirements.map((requirement) => (
        <div key={requirement.id} className="rounded-lg border bg-white p-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={requirement.category === "must_have" ? "brand" : "neutral"}>
              {categoryLabel(requirement.category)}
            </StatusBadge>
            {requirement.skill_normalized ? <span className="text-xs font-medium text-slate-500">{requirement.skill_normalized}</span> : null}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-700">{requirement.text}</p>
        </div>
      ))}
    </div>
  );
}

function parseStatusTone(status: ParseRunStatus): "neutral" | "brand" | "success" | "danger" {
  if (status === "succeeded") return "success";
  if (status === "failed" || status === "cancelled") return "danger";
  return status === "running" ? "brand" : "neutral";
}

function statusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function categoryLabel(category: string): string {
  return category.split("_").map(statusLabel).join(" ");
}
