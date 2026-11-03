"use client";

import { BriefcaseBusiness, ClipboardCheck, FolderGit2, LayoutDashboard, Library } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const navigation = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Jobs", href: "/jobs", icon: BriefcaseBusiness },
  { label: "Experiences", href: "/experiences", icon: Library },
  { label: "Projects", href: "/projects", icon: FolderGit2 },
  { label: "Action Items", href: "/action-items", icon: ClipboardCheck },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function PrimaryNav() {
  const pathname = usePathname();
  return (
    <nav
      className="flex gap-0.5 overflow-x-auto px-2 pb-2 [scrollbar-width:none] [mask-image:linear-gradient(to_right,black_85%,transparent)] lg:flex-1 lg:flex-col lg:overflow-visible lg:[mask-image:none]"
      aria-label="Primary"
    >
      {navigation.map(({ label, href, icon: Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex h-[30px] shrink-0 items-center gap-2 rounded-md px-2 text-sm transition-colors",
              active
                ? "bg-sidebar-elevated font-medium text-sidebar-foreground"
                : "text-sidebar-muted hover:bg-sidebar-elevated hover:text-sidebar-foreground",
            )}
          >
            <Icon className="size-[18px] text-faint" strokeWidth={1.75} aria-hidden="true" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

const titles: Record<string, string> = {
  dashboard: "Dashboard",
  jobs: "Jobs",
  experiences: "Experiences",
  projects: "Projects",
  "action-items": "Action Items",
};

export function WorkspaceTitle() {
  const pathname = usePathname();
  const [section, detail] = pathname.split("/").filter(Boolean);
  const title = titles[section ?? ""] ?? "Workspace";
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-0.5 text-sm">
      {detail ? (
        <>
          <Link href={`/${section}`} className="rounded px-1.5 py-0.5 text-muted transition hover:bg-hover hover:text-foreground">
            {title}
          </Link>
          <span className="text-faint">/</span>
          <span className="px-1.5 py-0.5">Details</span>
        </>
      ) : (
        <span className="px-1.5 py-0.5">{title}</span>
      )}
    </nav>
  );
}
