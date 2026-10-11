import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell/app-shell";
import { Card } from "@/components/ui/card";
import { getCurrentUser } from "@/lib/auth/current-user";
import { QueryProvider } from "@/providers/query-provider";

export default async function WorkspaceLayout({ children }: { children: ReactNode }) {
  const currentUser = await getCurrentUser();
  if (currentUser.kind === "unauthenticated") {
    redirect("/login?reason=expired");
  }

  if (currentUser.kind === "unavailable") {
    return (
      <main className="grid min-h-screen place-items-center px-5">
        <Card className="max-w-lg p-7">
          <p className="text-sm font-semibold text-[var(--danger)]">Service unavailable</p>
          <h1 className="mt-2 text-2xl font-semibold">CareerOps cannot reach its API.</h1>
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
            Your session has not been cleared. Start the local API and refresh this page.
          </p>
        </Card>
      </main>
    );
  }

  return (
    <QueryProvider>
      <AppShell email={currentUser.user.email}>{children}</AppShell>
    </QueryProvider>
  );
}
