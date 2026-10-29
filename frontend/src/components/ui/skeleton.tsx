import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-shimmer rounded-md bg-[linear-gradient(90deg,var(--surface-subtle)_0px,#ebebf0_120px,var(--surface-subtle)_240px)] bg-[length:800px_100%]",
        className,
      )}
      {...props}
    />
  );
}

export function LoadingCards({ label, count = 3 }: { label: string; count?: number }) {
  return (
    <div role="status" aria-live="polite" className="grid gap-3">
      <span className="sr-only">{label}</span>
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="rounded-xl border bg-surface p-5 shadow-card">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="mt-3 h-4 w-2/3" />
          <Skeleton className="mt-4 h-3 w-full" />
          <Skeleton className="mt-2 h-3 w-5/6" />
        </div>
      ))}
    </div>
  );
}
