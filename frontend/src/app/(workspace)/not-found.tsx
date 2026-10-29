import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

export default function WorkspaceNotFound() {
  return (
    <div className="max-w-xl">
      <span className="block text-[52px] leading-none" aria-hidden="true">🔎</span>
      <h1 className="mt-4 text-[32px] font-bold leading-tight tracking-tight">Page not found</h1>
      <p className="mt-2 text-[15px] leading-6 text-muted">This page does not exist, or it belongs to another account.</p>
      <Link href="/dashboard" className={buttonVariants({ className: "mt-6" })}>Back to dashboard</Link>
    </div>
  );
}
