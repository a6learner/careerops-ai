import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-55",
  {
    variants: {
      variant: {
        primary:
          "bg-[var(--brand)] text-white shadow-sm hover:bg-[var(--brand-strong)]",
        secondary:
          "border bg-white text-[var(--foreground)] shadow-sm hover:bg-[var(--surface-subtle)]",
        ghost: "text-[var(--muted)] hover:bg-black/5 hover:text-[var(--foreground)]",
        danger: "bg-[var(--danger)] text-white hover:bg-[#a8293c]",
      },
      size: {
        default: "h-10 px-4",
        sm: "h-9 px-3",
        lg: "h-11 px-5",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>;

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return (
    <button
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}
