import { ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
      <section className="hidden border-r bg-[#182033] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3 text-sm font-semibold tracking-wide">
          <span className="grid size-9 place-items-center rounded-xl bg-white/10">
            <ShieldCheck className="size-5" aria-hidden="true" />
          </span>
          CareerOps AI
        </div>
        <div className="max-w-xl">
          <p className="mb-5 text-sm font-semibold uppercase tracking-[0.22em] text-indigo-200">
            Evidence-first career operations
          </p>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight">
            Turn job requirements into a grounded preparation plan.
          </h1>
          <p className="mt-5 max-w-lg text-base leading-7 text-slate-300">
            Keep every recommendation connected to experience you can actually explain in an
            interview.
          </p>
        </div>
        <p className="text-xs text-slate-400">Reliable backend. Traceable evidence. Clear next steps.</p>
      </section>
      <section className="flex min-h-screen items-center justify-center px-5 py-12 sm:px-8">
        <div className="w-full max-w-md">{children}</div>
      </section>
    </main>
  );
}
