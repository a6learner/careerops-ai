"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Building2, CalendarClock, CircleDot, Clock3, ExternalLink, FileText, Link2, MapPin, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { ApiFeedback } from "@/components/api-feedback";
import { formatTimestamp, safeExternalUrl } from "@/components/jobs/job-format";
import { JobStatusSelect } from "@/components/jobs/job-status-select";
import { CompanyMark, DeadlineLabel } from "@/components/jobs/jobs-manager";
import { ParseRunPanel } from "@/components/jobs/parse-run-panel";
import { Card } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError, apiRequest } from "@/lib/api/client";
import type { Job } from "@/lib/api/types";

const DESCRIPTION_PREVIEW_CHARS = 600;

export function JobDetail({ jobId }: { jobId: string }) {
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => apiRequest<Job>(`/api/v1/jobs/${jobId}`),
  });

  if (job.isPending) return <JobDetailSkeleton />;
  if (job.error) {
    const notFound = job.error instanceof ApiRequestError && job.error.status === 404;
    return (
      <div>
        <BackLink />
        <div className="mt-4">
          {notFound ? (
            <Card className="p-8 text-center">
              <p className="font-semibold">Job not found</p>
              <p className="mt-1.5 text-sm text-muted">It may have been deleted, or it belongs to another account.</p>
            </Card>
          ) : (
            <ApiFeedback error={job.error} onRetry={() => void job.refetch()} />
          )}
        </div>
      </div>
    );
  }

  const data = job.data;
  const sourceUrl = safeExternalUrl(data.source_url);

  return (
    <article>
      <BackLink />
      <div className="mt-6">
        <CompanyMark company={data.company} size="lg" />
        <h1 className="mt-4 text-[32px] font-bold leading-tight tracking-tight sm:text-[40px]">{data.title}</h1>
      </div>

      <dl className="mt-4 space-y-0.5 text-sm">
        <Property icon={CircleDot} label="Status">
          <JobStatusSelect key={data.version} job={data} variant="inline" />
        </Property>
        <Property icon={Building2} label="Company">{data.company}</Property>
        <Property icon={MapPin} label="Location">{data.location ?? <Empty />}</Property>
        <Property icon={CalendarClock} label="Deadline">{data.deadline ? <DeadlineLabel deadline={data.deadline} /> : <Empty />}</Property>
        <Property icon={Link2} label="Source">
          {sourceUrl ? (
            <a className="inline-flex items-center gap-1 text-foreground underline decoration-border-strong underline-offset-2 hover:decoration-foreground" href={sourceUrl} target="_blank" rel="noreferrer">
              {new URL(sourceUrl).hostname} <ExternalLink className="size-3 text-faint" aria-hidden="true" />
            </a>
          ) : <Empty />}
        </Property>
        <Property icon={Clock3} label="Updated">
          <span className="text-muted">{formatTimestamp(data.updated_at)} · v{data.version}</span>
        </Property>
      </dl>

      <div className="mt-6 space-y-8 border-t pt-8">
        <ParseRunPanel job={data} />
        <DescriptionCard description={data.raw_description} />
      </div>
    </article>
  );
}

function Property({ icon: Icon, label, children }: { icon: LucideIcon; label: string; children: ReactNode }) {
  return (
    <div className="flex min-h-[34px] items-center gap-2">
      <dt className="flex w-36 shrink-0 items-center gap-1.5 text-muted">
        <Icon className="size-4 text-faint" strokeWidth={1.75} aria-hidden="true" />
        {label}
      </dt>
      <dd className="min-w-0 flex-1 px-1">{children}</dd>
    </div>
  );
}

function Empty() {
  return <span className="text-faint">Empty</span>;
}

function DescriptionCard({ description }: { description: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = description.length > DESCRIPTION_PREVIEW_CHARS;
  const visible = expanded || !long ? description : `${description.slice(0, DESCRIPTION_PREVIEW_CHARS).trimEnd()}…`;
  return (
    <section>
      <SectionHeading icon={FileText} title="Job description" />
      <p className="mt-3 whitespace-pre-wrap text-[15px] leading-7">{visible}</p>
      {long ? (
        <button type="button" className="mt-2 rounded px-1 text-sm text-muted hover:bg-hover" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Show less" : "Show full description"}
        </button>
      ) : null}
    </section>
  );
}

function BackLink() {
  return (
    <Link href="/jobs" className="-ml-1.5 inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-sm text-muted transition-colors hover:bg-hover hover:text-foreground">
      <ArrowLeft className="size-4" aria-hidden="true" />
      All jobs
    </Link>
  );
}

function JobDetailSkeleton() {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">Loading job…</span>
      <Skeleton className="h-4 w-20" />
      <Skeleton className="mt-6 size-[72px] rounded-lg" />
      <Skeleton className="mt-4 h-9 w-80" />
      <div className="mt-6 space-y-3">
        {Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-4 w-72" />)}
      </div>
    </div>
  );
}
