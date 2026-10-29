import type { ReactNode } from "react";

type PageHeaderProps = {
  icon?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
};

export function PageHeader({ icon, title, description, actions }: PageHeaderProps) {
  return (
    <div>
      {icon ? (
        <span className="block text-[52px] leading-none" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[32px] font-bold leading-tight tracking-tight sm:text-[40px]">{title}</h1>
          {description ? <p className="mt-1.5 max-w-2xl text-[15px] leading-6 text-muted">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
    </div>
  );
}
