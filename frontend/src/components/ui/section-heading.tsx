import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

type SectionHeadingProps = {
  icon: LucideIcon;
  title: string;
  description?: string;
  actions?: ReactNode;
};

export function SectionHeading({ icon: Icon, title, description, actions }: SectionHeadingProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h2 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Icon className="size-5 text-faint" strokeWidth={1.75} aria-hidden="true" />
          {title}
        </h2>
        {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
