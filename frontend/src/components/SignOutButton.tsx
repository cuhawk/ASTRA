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
      className="text-zinc-300 hover:text-emerald-400 text-sm"
    >
      Sign out
    </button>
  );
}
