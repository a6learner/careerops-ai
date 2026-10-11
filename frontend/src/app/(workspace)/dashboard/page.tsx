import { ArrowRight, BriefcaseBusiness, ClipboardCheck, Library } from "lucide-react";
import Link from "next/link";

import { DashboardSummary } from "@/components/dashboard/dashboard-summary";
import { Card } from "@/components/ui/card";

const steps = [
  {
    title: "Build your evidence library",
    description: "Capture projects, work, research, and coursework you can defend in an interview.",
    href: "/experiences",
    label: "Experiences",
    icon: Library,
  },
  {
    title: "Add a target role",
    description: "Save the job description before parsing requirements or starting analysis.",
    href: "/jobs",
    label: "Jobs",
    icon: BriefcaseBusiness,
  },
  {
    title: "Turn gaps into work",
    description: "Track preparation tasks linked to explicit evidence gaps.",
    href: "/action-items",
    label: "Action Items",
    icon: ClipboardCheck,
  },
];

export default function DashboardPage() {
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Your evidence workspace</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
            Move from real experience evidence to job requirements, grounded analysis, and focused
            preparation tasks.
          </p>
        </div>
      </div>

      <DashboardSummary />

      <div className="mt-8 grid gap-4 lg:grid-cols-3">
        {steps.map(({ title, description, href, label, icon: Icon }, index) => (
          <Card key={href} className="group p-5 transition hover:-translate-y-0.5 hover:shadow-md">
            <div className="flex items-center justify-between">
              <span className="grid size-10 place-items-center rounded-xl bg-[var(--brand-soft)] text-[var(--brand)]">
                <Icon className="size-5" aria-hidden="true" />
              </span>
              <span className="text-xs font-semibold text-slate-400">0{index + 1}</span>
            </div>
            <h2 className="mt-5 font-semibold">{title}</h2>
            <p className="mt-2 min-h-12 text-sm leading-6 text-[var(--muted)]">{description}</p>
            <Link
              href={href}
              className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[var(--brand)]"
            >
              Open {label}
              <ArrowRight className="size-4 transition group-hover:translate-x-0.5" aria-hidden="true" />
            </Link>
          </Card>
        ))}
      </div>

    </div>
  );
}
