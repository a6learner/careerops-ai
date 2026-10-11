"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, SearchCheck } from "lucide-react";
import { useState } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiRequestError, apiRequest } from "@/lib/api/client";
import type {
  ActionItem,
  AnalysisRun,
  EvidenceMatch,
  Experience,
  ExperienceList,
  Job,
  JobRequirement,
  ParseRun,
  ParseRunStatus,
} from "@/lib/api/types";

const TERMINAL_STATUSES = new Set<ParseRunStatus>(["succeeded", "failed", "cancelled"]);

export function AnalysisRunPanel({ job, parseRun }: { job: Job; parseRun: ParseRun }) {
  const [submittedRun, setSubmittedRun] = useState<AnalysisRun | null>(null);
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const analysis = useQuery({
    queryKey: ["analysis-run", job.id, submittedRun?.id],
    queryFn: () => apiRequest<AnalysisRun>(`/api/v1/jobs/${job.id}/analysis-runs/${submittedRun?.id}`),
    enabled: submittedRun !== null,
    refetchInterval: (query) => {
      const run = query.state.data;
      return run && TERMINAL_STATUSES.has(run.status) ? false : 1_500;
    },
  });
  const submit = useMutation({
    mutationFn: (key: string) => apiRequest<AnalysisRun>(`/api/v1/jobs/${job.id}/analysis-runs`, {
      method: "POST",
      headers: { "content-type": "application/json", "idempotency-key": key },
      body: JSON.stringify({ parse_run_id: parseRun.id }),
    }),
    onSuccess: (run) => {
      setPendingKey(null);
      setSubmittedRun(run);
    },
  });
  const currentRun = analysis.data ?? submittedRun;
  const submitConflict = submit.error instanceof ApiRequestError && submit.error.status === 409;

  function submitWithKey(key: string) {
    setPendingKey(key);
    submit.mutate(key);
  }
  function startOrRetry() {
    submitWithKey(pendingKey ?? crypto.randomUUID());
  }
  function startNew() {
    setSubmittedRun(null);
    submit.reset();
    submitWithKey(crypto.randomUUID());
  }

  return (
    <div className="mt-5 border-t border-slate-200 pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">Evidence analysis</p>
          <p className="mt-1 text-xs text-[var(--muted)]">Match parsed requirements only to validated experience evidence.</p>
        </div>
        {!currentRun ? (
          <Button size="sm" disabled={submit.isPending} onClick={startOrRetry}>
            {submit.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <SearchCheck className="size-4" />}
            {submit.isPending ? "Submitting…" : "Analyze evidence"}
          </Button>
        ) : null}
      </div>

      {submit.error ? <div className="mt-4"><ApiFeedback error={submit.error} onRetry={submitConflict ? startNew : startOrRetry} /></div> : null}
      {analysis.error ? <div className="mt-4"><ApiFeedback error={analysis.error} onRetry={() => void analysis.refetch()} /></div> : null}
      {currentRun ? <AnalysisResult job={job} parseRun={parseRun} run={currentRun} isRefreshing={analysis.isFetching} onStartNew={startNew} /> : null}
    </div>
  );
}

function AnalysisResult({ job, parseRun, run, isRefreshing, onStartNew }: { job: Job; parseRun: ParseRun; run: AnalysisRun; isRefreshing: boolean; onStartNew: () => void }) {
  const experiences = useQuery({
    queryKey: ["experiences"],
    queryFn: () => apiRequest<ExperienceList>("/api/v1/experiences"),
    enabled: run.status === "succeeded",
  });
  const active = run.status === "queued" || run.status === "running";
  return (
    <div className="mt-4 rounded-lg border bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <StatusBadge tone={runTone(run.status)}>{label(run.status)}</StatusBadge>
          {active && isRefreshing ? <LoaderCircle aria-label="Checking analysis status" className="size-4 animate-spin text-[var(--brand)]" /> : null}
          <span className="text-xs text-[var(--muted)]">Attempt {run.attempt}</span>
        </div>
        {TERMINAL_STATUSES.has(run.status) ? <Button size="sm" variant="ghost" onClick={onStartNew}>Analyze again</Button> : null}
      </div>
      {active ? <p className="mt-3 text-sm text-slate-600">Retrieval and matching are running in the worker.</p> : null}
      {run.status === "failed" ? <p className="mt-3 rounded-md bg-rose-50 p-3 text-sm text-rose-800">Analysis failed with code <span className="font-mono font-semibold">{run.error_code ?? "UNKNOWN"}</span>. No evidence claims are shown.</p> : null}
      {run.status === "cancelled" ? <p className="mt-3 text-sm text-slate-600">This analysis run was cancelled.</p> : null}
      {run.status === "succeeded" && experiences.error ? <div className="mt-4"><ApiFeedback error={experiences.error} onRetry={() => void experiences.refetch()} /></div> : null}
      {run.status === "succeeded" ? <EvidenceResults job={job} requirements={parseRun.requirements} matches={run.matches} experiences={experiences.data?.items ?? []} /> : null}
    </div>
  );
}

function EvidenceResults({ job, requirements, matches, experiences }: { job: Job; requirements: JobRequirement[]; matches: EvidenceMatch[]; experiences: Experience[] }) {
  const byRequirement = new Map(matches.map((match) => [match.requirement_id, match]));
  const byExperience = new Map(experiences.map((experience) => [experience.id, experience]));
  return (
    <div className="mt-4 space-y-3">
      {requirements.map((requirement) => {
        const match = byRequirement.get(requirement.id);
        const experience = match?.experience_id ? byExperience.get(match.experience_id) : undefined;
        return <EvidenceRow key={requirement.id} job={job} requirement={requirement} match={match} experience={experience} />;
      })}
    </div>
  );
}

function EvidenceRow({ job, requirement, match, experience }: { job: Job; requirement: JobRequirement; match?: EvidenceMatch; experience?: Experience }) {
  const verdict = match?.verdict ?? "insufficient_evidence";
  const positiveEvidence = match && (verdict === "matched" || verdict === "partial") && match.quote_valid && match.quote;
  return (
    <div className="rounded-lg border bg-slate-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-slate-800">{requirement.text}</p>
        <StatusBadge tone={verdictTone(verdict)}>{label(verdict)}</StatusBadge>
      </div>
      {positiveEvidence ? (
        <div className="mt-3 rounded-md border-l-2 border-emerald-400 bg-white p-3">
          <p className="text-xs font-semibold text-emerald-800">{experience?.title ?? "Validated experience"} · version {match.experience_version}</p>
          <blockquote className="mt-1 text-sm text-slate-700">“{match.quote}”</blockquote>
        </div>
      ) : (
        <p className="mt-2 text-sm text-slate-600">No validated positive evidence is available for this requirement.</p>
      )}
      {match && verdict !== "matched" ? <GapTaskButton jobId={job.id} matchId={match.id} requirementText={requirement.text} /> : null}
    </div>
  );
}

function GapTaskButton({ jobId, matchId, requirementText }: { jobId: string; matchId: string; requirementText: string }) {
  const queryClient = useQueryClient();
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: (key: string) => apiRequest<ActionItem>("/api/v1/action-items", {
      method: "POST",
      headers: { "content-type": "application/json", "idempotency-key": key },
      body: JSON.stringify({ job_id: jobId, title: gapTitle(requirementText), source_evidence_match_id: matchId }),
    }),
    onSuccess: async () => {
      setPendingKey(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["action-items"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
  });
  function startOrRetry() {
    const key = pendingKey ?? crypto.randomUUID();
    setPendingKey(key);
    create.mutate(key);
  }
  if (create.isSuccess) return <p className="mt-3 text-xs font-semibold text-[var(--success)]">Action item created.</p>;
  return (
    <div className="mt-3">
      <Button size="sm" variant="secondary" disabled={create.isPending} onClick={startOrRetry}>{create.isPending ? "Creating…" : "Create action item"}</Button>
      {create.error ? <div className="mt-3"><ApiFeedback error={create.error} onRetry={startOrRetry} /></div> : null}
    </div>
  );
}

function gapTitle(requirement: string): string {
  const prefix = "Address gap: ";
  return `${prefix}${requirement}`.slice(0, 200);
}

function runTone(status: ParseRunStatus): "neutral" | "brand" | "success" | "danger" {
  if (status === "succeeded") return "success";
  if (status === "failed" || status === "cancelled") return "danger";
  return status === "running" ? "brand" : "neutral";
}

function verdictTone(verdict: string): "neutral" | "brand" | "success" | "danger" {
  if (verdict === "matched") return "success";
  if (verdict === "partial") return "brand";
  return "danger";
}

function label(value: string): string {
  return value.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}
