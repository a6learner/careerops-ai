"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";

export function LogoutButton() {
  const router = useRouter();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  async function logout() {
    setIsLoggingOut(true);
    try {
      await fetch("/api/session/logout", { method: "POST" });
    } finally {
      window.localStorage.removeItem("careerops.run-pointers");
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="w-full justify-start"
      onClick={logout}
      disabled={isLoggingOut}
    >
      <LogOut className="size-4" aria-hidden="true" />
      {isLoggingOut ? "Signing out…" : "Sign out"}
    </Button>
  );
}
