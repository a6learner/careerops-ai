"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ListChecks, LoaderCircle, Play, RotateCcw } from "lucide-react";
import { useState } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { AnalysisRunPanel } from "@/components/jobs/analysis-run-panel";
import { humanize, RunFailure, runStatusTone, TERMINAL_RUN_STATUSES } from "@/components/jobs/run-status";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, type TagColor } from "@/components/ui/status-badge";
import { ApiRequestError, apiRequest, apiRequestOrNull } from "@/lib/api/client";
import type { Job, JobRequirement, ParseRun } from "@/lib/api/types";

const CATEGORY_ORDER = ["must_have", "nice_to_have", "responsibility", "education"] as const;
const CATEGORY_COLORS: Record<(typeof CATEGORY_ORDER)[number], TagColor> = {
  must_have: "red",
  nice_to_have: "blue",
  responsibility: "gray",
  education: "brown",
};

export function ParseRunPanel({ job }: { job: Job }) {
  const [submittedRun, setSubmittedRun] = useState<ParseRun | null>(null);
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [replacingLatest, setReplacingLatest] = useState(false);

  const latest = useQuery({
    queryKey: ["parse-run", job.id, "latest"],
    queryFn: () => apiRequestOrNull<ParseRun>(`/api/v1/jobs/${job.id}/parse-runs/latest`, "PARSE_RUN_NOT_FOUND"),
  });
  const restoredRun = replacingLatest ? null : (latest.data ?? null);
  const trackedRun = submittedRun ?? restoredRun;

  const runQuery = useQuery({
    queryKey: ["parse-run", job.id, trackedRun?.id],
    queryFn: () =>
      apiRequest<ParseRun>(`/api/v1/jobs/${job.id}/parse-runs/${trackedRun?.id}`),
    enabled: trackedRun !== null,
    initialData: trackedRun ?? undefined,
    refetchInterval: (query) => {
      const run = query.state.data;
      return run && TERMINAL_RUN_STATUSES.has(run.status) ? false : 1_500;
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

  const currentRun = trackedRun ? (runQuery.data ?? trackedRun) : null;

  function submitWithKey(idempotencyKey: string) {
    setPendingKey(idempotencyKey);
    submit.mutate(idempotencyKey);
  }

  function startOrRetry() {
    submitWithKey(pendingKey ?? crypto.randomUUID());
  }

  function startNewRun() {
    setReplacingLatest(true);
    setSubmittedRun(null);
    submit.reset();
    submitWithKey(crypto.randomUUID());
  }

  const submitConflict = submit.error instanceof ApiRequestError && submit.error.status === 409;
  const isActive = currentRun?.status === "queued" || currentRun?.status === "running";

  return (
    <>
      <section>
        <SectionHeading
          icon={ListChecks}
          title="Requirements"
          description="Parsed from the description by the worker, never by the API request."
          actions={currentRun ? (
            <>
              <StatusBadge tone={runStatusTone(currentRun.status)} dot>{humanize(currentRun.status)}</StatusBadge>
              {isActive && runQuery.isFetching ? <LoaderCircle aria-label="Checking parse status" className="size-4 animate-spin text-brand" /> : null}
              {TERMINAL_RUN_STATUSES.has(currentRun.status) ? (
                <Button size="sm" variant="ghost" onClick={startNewRun}><RotateCcw className="size-3.5" />Parse again</Button>
              ) : null}
            </>
          ) : latest.isPending ? null : (
            <Button size="sm" disabled={submit.isPending} onClick={startOrRetry}>
              {submit.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Play className="size-3.5" />}
              {submit.isPending ? "Submitting…" : "Parse description"}
            </Button>
          )}
        />
        <div className="mt-4 space-y-3">
          {submit.error ? (
            <ApiFeedback error={submit.error} onRetry={submitConflict ? startNewRun : startOrRetry} />
          ) : null}
          {runQuery.error ? <ApiFeedback error={runQuery.error} onRetry={() => void runQuery.refetch()} /> : null}
          {latest.error ? <ApiFeedback error={latest.error} onRetry={() => void latest.refetch()} /> : null}
          {latest.isPending && !currentRun ? (
            <div role="status" className="space-y-2">
              <span className="sr-only">Loading requirements…</span>
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          ) : null}
          {!currentRun && !latest.isPending && !latest.error && !submit.error ? (
            <Callout>Not parsed yet. Parsing extracts must-have and nice-to-have requirements with source spans.</Callout>
          ) : null}
          {currentRun ? <RunBody run={currentRun} /> : null}
        </div>
      </section>
      {currentRun?.status === "succeeded" ? <AnalysisRunPanel job={job} parseRun={currentRun} /> : null}
    </>
  );
}

function RunBody({ run }: { run: ParseRun }) {
  if (run.status === "queued" || run.status === "running") {
    return <Callout icon="⏳">Attempt {run.attempt}. The worker will update this view automatically.</Callout>;
  }
  if (run.status === "failed") return <RunFailure code={run.error_code} consequence="No requirements were saved." />;
  if (run.status === "cancelled") return <p className="text-sm text-muted">This parse run was cancelled before completion.</p>;
  return <Requirements requirements={run.requirements} />;
}

function Requirements({ requirements }: { requirements: JobRequirement[] }) {
  if (requirements.length === 0) {
    return <p className="text-sm text-muted">Parsing succeeded, but no requirements were found.</p>;
  }

  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    items: requirements.filter((requirement) => requirement.category === category),
  })).filter((group) => group.items.length > 0);

  return (
    <div className="space-y-4">
      {groups.map(({ category, items }) => (
        <section key={category}>
          <div className="flex items-center gap-2">
            <StatusBadge tone={CATEGORY_COLORS[category]}>{humanize(category)}</StatusBadge>
            <span className="text-xs text-faint">{items.length}</span>
          </div>
          <ul className="mt-1.5">
            {items.map((requirement) => (
              <li key={requirement.id} className="flex items-start gap-2 rounded-md px-1 py-1 hover:bg-hover">
                <span className="mt-[10px] size-1.5 shrink-0 rounded-full bg-foreground/70" aria-hidden="true" />
                <p className="min-w-0 flex-1 text-[15px] leading-6">{requirement.text}</p>
                {requirement.skill_normalized ? (
                  <code className="mt-0.5 shrink-0 rounded bg-[rgb(135_131_120/0.15)] px-1.5 py-0.5 font-mono text-xs text-[#eb5757]">{requirement.skill_normalized}</code>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
