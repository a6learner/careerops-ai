"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, LoaderCircle, RotateCcw, SearchCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { humanize, RunFailure, runStatusTone, TERMINAL_RUN_STATUSES } from "@/components/jobs/run-status";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, type BadgeTone } from "@/components/ui/status-badge";
import { useToast } from "@/components/ui/toast";
import { ApiRequestError, apiRequest, apiRequestOrNull } from "@/lib/api/client";
import type {
  ActionItem,
  AnalysisRun,
  EvidenceMatch,
  EvidenceVerdict,
  Experience,
  ExperienceList,
  Job,
  JobRequirement,
  ParseRun,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function AnalysisRunPanel({ job, parseRun }: { job: Job; parseRun: ParseRun }) {
  const [submittedRun, setSubmittedRun] = useState<AnalysisRun | null>(null);
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [replacingLatest, setReplacingLatest] = useState(false);
  const latest = useQuery({
    queryKey: ["analysis-run", job.id, "latest", parseRun.id],
    queryFn: () =>
      apiRequestOrNull<AnalysisRun>(
        `/api/v1/jobs/${job.id}/analysis-runs/latest?parse_run_id=${parseRun.id}`,
        "ANALYSIS_RUN_NOT_FOUND",
      ),
  });
  const restoredRun = replacingLatest ? null : (latest.data ?? null);
  const trackedRun = submittedRun ?? restoredRun;
  const analysis = useQuery({
    queryKey: ["analysis-run", job.id, trackedRun?.id],
    queryFn: () => apiRequest<AnalysisRun>(`/api/v1/jobs/${job.id}/analysis-runs/${trackedRun?.id}`),
    enabled: trackedRun !== null,
    initialData: trackedRun ?? undefined,
    refetchInterval: (query) => {
      const run = query.state.data;
      return run && TERMINAL_RUN_STATUSES.has(run.status) ? false : 1_500;
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
  const currentRun = trackedRun ? (analysis.data ?? trackedRun) : null;
  const submitConflict = submit.error instanceof ApiRequestError && submit.error.status === 409;
  const isActive = currentRun?.status === "queued" || currentRun?.status === "running";

  function submitWithKey(key: string) {
    setPendingKey(key);
    submit.mutate(key);
  }
  function startOrRetry() {
    submitWithKey(pendingKey ?? crypto.randomUUID());
  }
  function startNew() {
    setReplacingLatest(true);
    setSubmittedRun(null);
    submit.reset();
    submitWithKey(crypto.randomUUID());
  }

  return (
    <section>
      <SectionHeading
        icon={SearchCheck}
        title="Evidence & gaps"
        description="Requirements are matched only to validated quotes from your experiences."
        actions={currentRun ? (
          <>
            <StatusBadge tone={runStatusTone(currentRun.status)} dot>{humanize(currentRun.status)}</StatusBadge>
            {isActive && analysis.isFetching ? <LoaderCircle aria-label="Checking analysis status" className="size-4 animate-spin text-brand" /> : null}
            {TERMINAL_RUN_STATUSES.has(currentRun.status) ? (
              <Button size="sm" variant="ghost" onClick={startNew}><RotateCcw className="size-3.5" />Analyze again</Button>
            ) : null}
          </>
        ) : latest.isPending ? null : (
          <Button size="sm" disabled={submit.isPending} onClick={startOrRetry}>
            {submit.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <SearchCheck className="size-3.5" />}
            {submit.isPending ? "Submitting…" : "Analyze evidence"}
          </Button>
        )}
      />
      <div className="mt-4 space-y-3">
        {submit.error ? <ApiFeedback error={submit.error} onRetry={submitConflict ? startNew : startOrRetry} /> : null}
        {analysis.error ? <ApiFeedback error={analysis.error} onRetry={() => void analysis.refetch()} /> : null}
        {latest.error ? <ApiFeedback error={latest.error} onRetry={() => void latest.refetch()} /> : null}
        {latest.isPending && !currentRun ? (
          <div role="status" className="space-y-2">
            <span className="sr-only">Loading evidence…</span>
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : null}
        {!currentRun && !latest.isPending && !latest.error && !submit.error ? (
          <Callout>Run analysis to see which requirements your experience library supports and where the gaps are.</Callout>
        ) : null}
        {currentRun ? <AnalysisResult job={job} parseRun={parseRun} run={currentRun} /> : null}
      </div>
    </section>
  );
}

function AnalysisResult({ job, parseRun, run }: { job: Job; parseRun: ParseRun; run: AnalysisRun }) {
  const experiences = useQuery({
    queryKey: ["experiences"],
    queryFn: () => apiRequest<ExperienceList>("/api/v1/experiences"),
    enabled: run.status === "succeeded",
  });
  if (run.status === "queued" || run.status === "running") {
    return <Callout icon="⏳">Attempt {run.attempt}. Retrieval and matching are running in the worker.</Callout>;
  }
  if (run.status === "failed") return <RunFailure code={run.error_code} consequence="No evidence claims are shown." />;
  if (run.status === "cancelled") return <p className="text-sm text-muted">This analysis run was cancelled.</p>;
  return (
    <>
      {experiences.error ? <ApiFeedback error={experiences.error} onRetry={() => void experiences.refetch()} /> : null}
      <EvidenceResults job={job} requirements={parseRun.requirements} matches={run.matches} experiences={experiences.data?.items ?? []} />
    </>
  );
}

const VERDICT_SUMMARY: { verdicts: EvidenceVerdict[]; label: string; tone: string }[] = [
  { verdicts: ["matched"], label: "Supported", tone: "bg-[#448361]" },
  { verdicts: ["partial"], label: "Partial", tone: "bg-[#cb912f]" },
  { verdicts: ["missing", "insufficient_evidence"], label: "Gaps", tone: "bg-[#d44c47]" },
];

function EvidenceResults({ job, requirements, matches, experiences }: { job: Job; requirements: JobRequirement[]; matches: EvidenceMatch[]; experiences: Experience[] }) {
  const byRequirement = new Map(matches.map((match) => [match.requirement_id, match]));
  const byExperience = new Map(experiences.map((experience) => [experience.id, experience]));
  const verdictOf = (requirement: JobRequirement): EvidenceVerdict => byRequirement.get(requirement.id)?.verdict ?? "insufficient_evidence";
  return (
    <>
      <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
        {VERDICT_SUMMARY.map(({ verdicts, label: summaryLabel, tone }) => (
          <span key={summaryLabel} className="inline-flex items-center gap-1.5 text-muted">
            <span className={cn("size-2 rounded-full", tone)} aria-hidden="true" />
            {summaryLabel}
            <span className="font-semibold text-foreground tabular-nums">
              {requirements.filter((requirement) => verdicts.includes(verdictOf(requirement))).length}
            </span>
          </span>
        ))}
      </div>
      <ul className="divide-y border-y">
        {requirements.map((requirement) => {
          const match = byRequirement.get(requirement.id);
          const experience = match?.experience_id ? byExperience.get(match.experience_id) : undefined;
          return <EvidenceRow key={requirement.id} job={job} requirement={requirement} match={match} experience={experience} />;
        })}
      </ul>
    </>
  );
}

function EvidenceRow({ job, requirement, match, experience }: { job: Job; requirement: JobRequirement; match?: EvidenceMatch; experience?: Experience }) {
  const verdict = match?.verdict ?? "insufficient_evidence";
  const positiveEvidence = match && (verdict === "matched" || verdict === "partial") && match.quote_valid && match.quote;
  return (
    <li className="py-3.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-[15px] font-medium leading-6">{requirement.text}</p>
        <StatusBadge tone={verdictTone(verdict)}>{verdictLabel(verdict)}</StatusBadge>
      </div>
      {positiveEvidence ? (
        <figure className="mt-2">
          <blockquote className="border-l-[3px] border-foreground pl-3.5 text-[15px] leading-6">{match.quote}</blockquote>
          <figcaption className="mt-1.5 pl-[17px] text-xs text-muted">
            from{" "}
            <Link href={match.experience_id ? `/experiences#experience-${match.experience_id}` : "/experiences"} className="text-foreground underline decoration-border-strong underline-offset-2 hover:decoration-foreground">
              {experience?.title ?? "Validated experience"}
            </Link>{" "}
            · version {match.experience_version}
          </figcaption>
        </figure>
      ) : (
        <p className="mt-1.5 text-sm text-muted">No validated positive evidence is available for this requirement.</p>
      )}
      {match && verdict !== "matched" ? <GapTaskButton jobId={job.id} matchId={match.id} requirementText={requirement.text} /> : null}
    </li>
  );
}

function GapTaskButton({ jobId, matchId, requirementText }: { jobId: string; matchId: string; requirementText: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: (key: string) => apiRequest<ActionItem>("/api/v1/action-items", {
      method: "POST",
      headers: { "content-type": "application/json", "idempotency-key": key },
      body: JSON.stringify({ job_id: jobId, title: gapTitle(requirementText), source_evidence_match_id: matchId }),
    }),
    onSuccess: async () => {
      setPendingKey(null);
      toast({ tone: "success", title: "Action item created", description: "Track it under Action Items." });
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
  if (create.isSuccess) {
    return <p className="mt-2.5 inline-flex items-center gap-1.5 text-xs font-medium text-success"><Check className="size-3.5" aria-hidden="true" />Action item created.</p>;
  }
  return (
    <div className="mt-2.5">
      <Button size="sm" variant="secondary" disabled={create.isPending} onClick={startOrRetry}>{create.isPending ? "Creating…" : "Create action item"}</Button>
      {create.error ? <div className="mt-3"><ApiFeedback error={create.error} onRetry={startOrRetry} /></div> : null}
    </div>
  );
}

function gapTitle(requirement: string): string {
  const prefix = "Address gap: ";
  return `${prefix}${requirement}`.slice(0, 200);
}

function verdictTone(verdict: EvidenceVerdict): BadgeTone {
  if (verdict === "matched") return "green";
  if (verdict === "partial") return "yellow";
  return "red";
}

function verdictLabel(verdict: EvidenceVerdict): string {
  return verdict === "insufficient_evidence" ? "Insufficient evidence" : humanize(verdict);
}
