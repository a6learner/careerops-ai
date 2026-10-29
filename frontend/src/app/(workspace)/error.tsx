"use client";

import { Button } from "@/components/ui/button";

export default function WorkspaceError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="max-w-xl">
      <span className="block text-[52px] leading-none" aria-hidden="true">⚠️</span>
      <h1 className="mt-4 text-[32px] font-bold leading-tight tracking-tight">This page failed to load</h1>
      <p className="mt-2 text-[15px] leading-6 text-muted">
        Your saved data is unchanged. Try again; if it keeps failing, check that the local API and worker are running.
      </p>
      {error.digest ? <p className="mt-3 font-mono text-xs text-faint">Reference: {error.digest}</p> : null}
      <Button className="mt-6" onClick={reset}>Try again</Button>
    </div>
  );
}
