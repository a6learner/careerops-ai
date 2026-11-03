import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export type TagColor = "gray" | "brown" | "orange" | "yellow" | "green" | "blue" | "purple" | "pink" | "red";
type SemanticTone = "neutral" | "brand" | "success" | "danger" | "warning" | "info";
export type BadgeTone = TagColor | SemanticTone;

const semanticColors: Record<SemanticTone, TagColor> = {
  neutral: "gray",
  brand: "blue",
  success: "green",
  danger: "red",
  warning: "orange",
  info: "purple",
};

const colorClasses: Record<TagColor, string> = {
  gray: "bg-[var(--tag-gray-bg)] text-[var(--tag-gray-fg)]",
  brown: "bg-[var(--tag-brown-bg)] text-[var(--tag-brown-fg)]",
  orange: "bg-[var(--tag-orange-bg)] text-[var(--tag-orange-fg)]",
  yellow: "bg-[var(--tag-yellow-bg)] text-[var(--tag-yellow-fg)]",
  green: "bg-[var(--tag-green-bg)] text-[var(--tag-green-fg)]",
  blue: "bg-[var(--tag-blue-bg)] text-[var(--tag-blue-fg)]",
  purple: "bg-[var(--tag-purple-bg)] text-[var(--tag-purple-fg)]",
  pink: "bg-[var(--tag-pink-bg)] text-[var(--tag-pink-fg)]",
  red: "bg-[var(--tag-red-bg)] text-[var(--tag-red-fg)]",
};

type StatusBadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: BadgeTone;
  dot?: boolean;
};

export function tagColor(tone: BadgeTone): TagColor {
  return tone in semanticColors ? semanticColors[tone as SemanticTone] : (tone as TagColor);
}

export function StatusBadge({ className, tone = "neutral", dot = false, children, ...props }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center gap-1.5 whitespace-nowrap rounded-[4px] px-1.5 text-xs leading-5",
        colorClasses[tagColor(tone)],
        className,
      )}
      {...props}
    >
      {dot ? <span className="size-1.5 rounded-full bg-current opacity-70" aria-hidden="true" /> : null}
      {children}
    </span>
  );
}
