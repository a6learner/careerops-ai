import type { TextareaHTMLAttributes } from "react";

import { fieldClassName } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(fieldClassName, "min-h-24 py-2 leading-6", className)} {...props} />;
}
