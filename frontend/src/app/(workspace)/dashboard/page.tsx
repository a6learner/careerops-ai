import { ArrowUpRight, BriefcaseBusiness, ClipboardCheck, FolderGit2, Library } from "lucide-react";
import Link from "next/link";

import { DashboardFocus } from "@/components/dashboard/dashboard-focus";
import { DashboardSummary } from "@/components/dashboard/dashboard-summary";
import { PageHeader } from "@/components/ui/page-header";

const steps = [
  {
    title: "Build your evidence library",
    description: "Capture projects, work, research and coursework you can defend in an interview.",
    href: "/experiences",
    icon: Library,
  },
  {
    title: "Add a target role",
    description: "Save the job description, then parse requirements and run analysis.",
    href: "/jobs",
    icon: BriefcaseBusiness,
  },
  {
    title: "Record project stages",
    description: "Keep decisions, failures and source excerpts while the work is fresh.",
    href: "/projects",
    icon: FolderGit2,
  },
  {
    title: "Turn gaps into work",
    description: "Track preparation tasks linked to explicit evidence gaps.",
    href: "/action-items",
    icon: ClipboardCheck,
  },
];

export default function DashboardPage() {
  return (
    <div>
      <PageHeader
        icon="🧭"
        title="Your evidence workspace"
        description="Move from real experience evidence to job requirements, grounded analysis and focused preparation tasks."
      />

      <DashboardSummary />

      <DashboardFocus />

      <section className="mt-10" aria-labelledby="workflow-heading">
        <h2 id="workflow-heading" className="border-b pb-2 text-lg font-semibold">Workflow</h2>
        <ol className="mt-2">
          {steps.map(({ title, description, href, icon: Icon }, index) => (
            <li key={href}>
              <Link
                href={href}
                className="group flex items-start gap-3 rounded-md px-2 py-2.5 transition-colors hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
              >
                <Icon className="mt-0.5 size-[18px] shrink-0 text-faint" strokeWidth={1.75} aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">
                    <span className="mr-1.5 text-faint">{index + 1}.</span>
                    {title}
                  </span>
                  <span className="block text-[13px] leading-5 text-muted">{description}</span>
                </span>
                <ArrowUpRight className="mt-0.5 size-4 text-faint opacity-0 transition group-hover:opacity-100" aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
