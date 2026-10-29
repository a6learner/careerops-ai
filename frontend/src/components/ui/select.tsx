import { ChevronDown } from "lucide-react";
import type { SelectHTMLAttributes } from "react";

import { fieldClassName } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className={cn("relative", className)}>
      <select className={cn(fieldClassName, "h-8 cursor-pointer appearance-none pr-7")} {...props}>
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-2 top-1/2 size-4 -translate-y-1/2 text-muted"
        aria-hidden="true"
      />
    </div>
  );
}
