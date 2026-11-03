import type { ReactNode } from "react";

type FieldProps = {
  label: string;
  hint?: string;
  htmlFor: string;
  children: ReactNode;
};

export function Field({ label, hint, htmlFor, children }: FieldProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between gap-3 text-sm">
        <label className="text-[13px] text-muted" htmlFor={htmlFor}>{label}</label>
        {hint ? <span className="text-xs text-faint">{hint}</span> : null}
      </div>
      {children}
    </div>
  );
}
