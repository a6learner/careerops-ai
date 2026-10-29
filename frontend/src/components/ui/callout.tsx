import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Callout({ icon = "💡", children, className }: { icon?: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn("flex gap-3 rounded-md bg-surface-subtle px-4 py-3.5 text-sm leading-6", className)}>
      <span className="text-base leading-6" aria-hidden="true">{icon}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
