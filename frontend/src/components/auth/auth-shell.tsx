import type { ReactNode } from "react";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col bg-surface">
      <header className="flex h-14 items-center gap-2 px-5 sm:px-8">
        <span className="grid size-[22px] place-items-center rounded-[4px] bg-foreground text-[11px] font-bold text-white">C</span>
        <span className="text-sm font-semibold">CareerOps</span>
      </header>
      <section className="flex flex-1 items-start justify-center px-5 pt-[12vh] pb-16">
        <div className="w-full max-w-[340px]">{children}</div>
      </section>
      <footer className="px-5 pb-6 text-center text-xs text-faint">
        Every positive claim is backed by a validated quote from your own experience.
      </footer>
    </main>
  );
}
