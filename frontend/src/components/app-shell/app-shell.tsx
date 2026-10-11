import { BriefcaseBusiness, ClipboardCheck, LayoutDashboard, Library, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { LogoutButton } from "@/components/app-shell/logout-button";

const navigation = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Jobs", href: "/jobs", icon: BriefcaseBusiness },
  { label: "Experiences", href: "/experiences", icon: Library },
  { label: "Action Items", href: "/action-items", icon: ClipboardCheck },
];

type AppShellProps = {
  email: string;
  children: ReactNode;
};

export function AppShell({ email, children }: AppShellProps) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      <aside className="border-b bg-white lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:border-b-0 lg:border-r">
        <div className="flex h-16 items-center gap-3 border-b px-5">
          <span className="grid size-9 place-items-center rounded-xl bg-[var(--brand)] text-white shadow-sm">
            <ShieldCheck className="size-5" aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-semibold">CareerOps AI</p>
            <p className="text-xs text-[var(--muted)]">Evidence workspace</p>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto p-3 lg:flex-1 lg:flex-col" aria-label="Primary">
          {navigation.map(({ label, href, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="flex shrink-0 items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-950"
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </Link>
          ))}
        </nav>
        <div className="hidden border-t p-3 lg:block">
          <p className="truncate px-3 pb-2 text-xs text-[var(--muted)]" title={email}>
            {email}
          </p>
          <LogoutButton />
        </div>
      </aside>
      <div className="min-w-0">
        <header className="flex h-16 items-center justify-between border-b bg-white/80 px-5 backdrop-blur lg:px-8">
          <p className="text-sm text-[var(--muted)]">Local workspace</p>
          <div className="lg:hidden">
            <LogoutButton />
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-5 py-8 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
