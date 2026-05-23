"use client";

import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export function SignOutButton() {
  const router = useRouter();
  async function onClick() {
    try {
      await api<void>("/auth/logout", { method: "POST" });
    } catch {
      // ignore — best-effort logout
    }
    router.push("/");
    router.refresh();
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-ink-mute hover:text-accent uppercase tracking-wider transition-colors"
    >
      sign out
    </button>
  );
}
