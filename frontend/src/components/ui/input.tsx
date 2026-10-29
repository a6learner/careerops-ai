import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export const fieldClassName =
  "w-full rounded-md border-0 bg-[rgb(242_241_238/0.6)] px-2.5 text-sm shadow-[inset_0_0_0_1px_rgb(15_15_15/0.1)] outline-none transition placeholder:text-faint focus:bg-surface focus:shadow-[inset_0_0_0_1px_var(--brand),0_0_0_3px_rgb(35_131_226/0.2)] disabled:cursor-not-allowed disabled:opacity-60";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(fieldClassName, "h-8", className)} {...props} />;
}
