import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type StatusBadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "brand" | "success" | "danger";
};

const tones = {
  neutral: "bg-slate-100 text-slate-600",
  brand: "bg-[var(--brand-soft)] text-[var(--brand-strong)]",
  success: "bg-[var(--success-soft)] text-[var(--success)]",
  danger: "bg-[var(--danger-soft)] text-[var(--danger)]",
};

export function StatusBadge({ className, tone = "neutral", ...props }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
