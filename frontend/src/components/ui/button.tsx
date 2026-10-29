import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex select-none items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 disabled:pointer-events-none disabled:opacity-45 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-brand text-white shadow-[inset_0_0_0_1px_rgb(15_15_15/0.1),0_1px_2px_rgb(15_15_15/0.1)] hover:bg-brand-strong",
        secondary: "bg-surface text-foreground shadow-[inset_0_0_0_1px_rgb(15_15_15/0.1),0_1px_2px_rgb(15_15_15/0.06)] hover:bg-hover",
        ghost: "text-muted hover:bg-hover hover:text-foreground",
        danger: "bg-danger text-white hover:bg-danger-strong",
        "danger-outline": "bg-surface text-danger shadow-[inset_0_0_0_1px_rgb(212_76_71/0.4)] hover:bg-danger-soft",
      },
      size: {
        default: "h-8 px-3",
        sm: "h-7 px-2 text-[13px]",
        lg: "h-9 px-4",
        icon: "size-7",
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
