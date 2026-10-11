import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-lg border bg-white px-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-[var(--brand)] focus:ring-3 focus:ring-[var(--brand-soft)] disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    />
  );
}
