import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
};

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("rounded-md bg-surface-subtle px-6 py-10 text-center", className)}>
      <span className="mx-auto grid size-10 place-items-center text-faint">
        <Icon className="size-7" strokeWidth={1.5} aria-hidden="true" />
      </span>
      <p className="mt-4 text-sm font-semibold">{title}</p>
      {description ? <p className="mx-auto mt-1.5 max-w-sm text-sm leading-6 text-muted">{description}</p> : null}
      {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
    </div>
  );
}
