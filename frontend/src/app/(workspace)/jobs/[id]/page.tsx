import type { Metadata } from "next";

import { JobDetail } from "@/components/jobs/job-detail";

export const metadata: Metadata = { title: "Job" };

export default async function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <JobDetail jobId={id} />;
}
