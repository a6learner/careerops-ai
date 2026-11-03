"use client";

import { ArrowRight, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { readApiError } from "@/lib/api/errors";

type AuthMode = "login" | "register";

type AuthFormProps = {
  mode: AuthMode;
  initialMessage?: string;
};

export function AuthForm({ mode, initialMessage }: AuthFormProps) {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isRegister = mode === "register";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    const form = new FormData(event.currentTarget);
    const credentials = {
      email: String(form.get("email") ?? ""),
      password: String(form.get("password") ?? ""),
    };

    try {
      if (isRegister) {
        const registration = await fetch("/api/session/register", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(credentials),
        });
        if (!registration.ok) {
          const apiError = await readApiError(registration);
          setError(`${apiError.message} Request ID: ${apiError.request_id}`);
          return;
        }
      }

      const login = await fetch("/api/session/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(credentials),
      });
      if (!login.ok) {
        const apiError = await readApiError(login);
        const prefix = isRegister ? "Your account was created, but sign-in failed. " : "";
        setError(`${prefix}${apiError.message} Request ID: ${apiError.request_id}`);
        return;
      }

      router.replace("/dashboard");
      router.refresh();
    } catch {
      setError("The request could not reach CareerOps. Your form has been preserved.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <h2 className="text-[26px] font-bold leading-tight tracking-tight">
        {isRegister ? "Start with real evidence" : "Sign in to CareerOps"}
      </h2>
      <p className="mt-1.5 text-[15px] leading-6 text-muted">
        {isRegister
          ? "Build your experience library, analyze target roles, and turn gaps into action."
          : "Continue managing your experience evidence and application workflow."}
      </p>

      {initialMessage ? (
        <div className="mt-6 rounded-md bg-brand-soft px-3.5 py-2.5 text-sm text-[var(--tag-blue-fg)]">
          {initialMessage}
        </div>
      ) : null}

      {error ? (
        <div
          role="alert"
          className="mt-6 rounded-md bg-danger-soft px-3.5 py-2.5 text-sm leading-6 text-danger"
        >
          {error}
        </div>
      ) : null}

      <form className="mt-7 space-y-4" onSubmit={submit}>
        <div className="space-y-1.5">
          <label className="text-xs text-muted" htmlFor={`${mode}-email`}>
            Email address
          </label>
          <Input
            id={`${mode}-email`}
            name="email"
            type="email"
            autoComplete="email"
            required
            disabled={isSubmitting}
            placeholder="you@example.com"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs text-muted" htmlFor={`${mode}-password`}>
            Password
          </label>
          <Input
            id={`${mode}-password`}
            name="password"
            type="password"
            autoComplete={isRegister ? "new-password" : "current-password"}
            minLength={isRegister ? 8 : 1}
            maxLength={128}
            required
            disabled={isSubmitting}
            placeholder={isRegister ? "At least 8 characters" : "Enter your password"}
          />
        </div>
        <Button className="mt-1 w-full" size="lg" disabled={isSubmitting}>
          {isSubmitting ? (
            <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <ArrowRight className="size-4" aria-hidden="true" />
          )}
          {isSubmitting
            ? isRegister
              ? "Creating account…"
              : "Signing in…"
            : isRegister
              ? "Create account"
              : "Sign in"}
        </Button>
      </form>

      <p className="mt-6 text-sm text-muted">
        {isRegister ? "Already have an account?" : "New to CareerOps?"}{" "}
        <Link
          href={isRegister ? "/login" : "/register"}
          className="text-foreground underline decoration-border-strong underline-offset-2 hover:decoration-foreground"
        >
          {isRegister ? "Sign in" : "Create an account"}
        </Link>
      </p>
    </div>
  );
}
