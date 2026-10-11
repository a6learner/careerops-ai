import type { Metadata } from "next";

import { AuthForm } from "@/components/auth/auth-form";

export const metadata: Metadata = { title: "Sign in" };

type LoginPageProps = {
  searchParams: Promise<{ reason?: string }>;
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const { reason } = await searchParams;
  const initialMessage =
    reason === "expired" ? "Your session expired. Sign in again to continue." : undefined;
  return <AuthForm mode="login" initialMessage={initialMessage} />;
}
