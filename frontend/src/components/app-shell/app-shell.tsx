import type { ReactNode } from "react";

import { LogoutButton } from "@/components/app-shell/logout-button";
import { PrimaryNav, WorkspaceTitle } from "@/components/app-shell/primary-nav";
import { ToastProvider } from "@/components/ui/toast";

type AppShellProps = {
  email: string;
  children: ReactNode;
};

export function AppShell({ email, children }: AppShellProps) {
  return (
    <ToastProvider>
      <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr] lg:bg-[linear-gradient(to_right,var(--sidebar)_240px,transparent_240px)]">
        <aside className="border-b border-sidebar-border bg-sidebar text-sidebar-foreground lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:border-r lg:border-b-0">
          <div className="flex items-center justify-between gap-2 px-3 pt-3 pb-1 lg:pb-2">
            <div className="flex min-w-0 items-center gap-2 rounded-md px-2 py-1.5">
              <span className="grid size-[22px] shrink-0 place-items-center rounded-[4px] bg-foreground text-[11px] font-bold text-white">C</span>
              <p className="truncate text-sm font-semibold">CareerOps</p>
            </div>
            <div className="lg:hidden">
              <LogoutButton compact />
            </div>
          </div>
          <PrimaryNav />
          <div className="mt-auto hidden p-2 lg:block">
            <div className="flex items-center gap-2 px-2 py-1.5">
              <span className="grid size-5 shrink-0 place-items-center rounded-full bg-[var(--tag-gray-bg)] text-[10px] font-semibold uppercase">
                {email.slice(0, 1)}
              </span>
              <p className="min-w-0 truncate text-xs text-sidebar-muted" title={email}>
                {email}
              </p>
            </div>
            <LogoutButton />
          </div>
        </aside>
        <div className="min-w-0">
          <header className="sticky top-0 z-20 hidden h-11 items-center bg-background/90 px-4 backdrop-blur lg:flex">
            <WorkspaceTitle />
          </header>
          <main className="mx-auto max-w-6xl px-4 pt-8 pb-16 sm:px-8 lg:px-24 lg:pt-14">{children}</main>
        </div>
      </div>
    </ToastProvider>
  );
}
