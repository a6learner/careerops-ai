import { Skeleton } from "@/components/ui/skeleton";

export default function WorkspaceLoading() {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">Loading page…</span>
      <Skeleton className="size-12 rounded-lg" />
      <Skeleton className="mt-5 h-9 w-72" />
      <Skeleton className="mt-3 h-4 w-96 max-w-full" />
      <div className="mt-10 grid grid-cols-2 gap-3 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-24 rounded-lg" />)}
      </div>
    </div>
  );
}
