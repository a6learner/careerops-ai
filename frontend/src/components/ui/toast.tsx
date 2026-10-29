"use client";

import { CheckCircle2, CircleAlert, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type ToastTone = "success" | "error";
type ToastMessage = { id: number; tone: ToastTone; title: string; description?: string };
type ToastInput = Omit<ToastMessage, "id">;

const TOAST_DURATION_MS = 3500;
const MAX_VISIBLE_TOASTS = 3;

const ToastContext = createContext<((toast: ToastInput) => void) | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback(
    (toast: ToastInput) => {
      nextId.current += 1;
      const id = nextId.current;
      setToasts((current) => [...current, { ...toast, id }].slice(-MAX_VISIBLE_TOASTS));
      window.setTimeout(() => dismiss(id), TOAST_DURATION_MS);
    },
    [dismiss],
  );

  const value = useMemo(() => show, [show]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2 sm:inset-x-auto sm:right-6 sm:bottom-6"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className="pointer-events-auto flex w-full max-w-sm animate-toast-in items-start gap-3 rounded-lg bg-surface p-3 shadow-raised"
          >
            {toast.tone === "success" ? (
              <CheckCircle2 className="mt-0.5 size-4 text-success" aria-hidden="true" />
            ) : (
              <CircleAlert className="mt-0.5 size-4 text-danger" aria-hidden="true" />
            )}
            <div className="min-w-0 flex-1">
              <p className={cn("text-sm font-medium", toast.tone === "error" && "text-danger")}>{toast.title}</p>
              {toast.description ? <p className="mt-0.5 text-xs leading-5 text-muted">{toast.description}</p> : null}
            </div>
            <button
              type="button"
              className="rounded-md p-0.5 text-muted transition hover:bg-foreground/5 hover:text-foreground"
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

const noop = () => undefined;

// Components rendered outside the provider (isolated unit tests) get a no-op instead of throwing.
export function useToast(): (toast: ToastInput) => void {
  return useContext(ToastContext) ?? noop;
}
