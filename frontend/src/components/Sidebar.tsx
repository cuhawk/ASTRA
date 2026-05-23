import Link from "next/link";
import { apiServer } from "@/lib/api-server";
import type { User } from "@/lib/types";
import { SignOutButton } from "./SignOutButton";
import { Wordmark } from "./Wordmark";
import { SidebarNav } from "./SidebarNav";

async function getUser(): Promise<User | null> {
  try {
    return await apiServer<User>("/auth/me");
  } catch {
    return null;
  }
}

export async function Sidebar() {
  const user = await getUser();
  return (
    <aside className="hidden md:flex fixed inset-y-0 left-0 z-30 w-60 flex-col border-r border-hair/60 bg-void/85 backdrop-blur-md">
      <div className="px-5 pt-6 pb-5 border-b border-hair/40 shrink-0">
        <Link
          href="/"
          className="flex items-center gap-2.5 group"
          aria-label="ASTRA home"
        >
          <Wordmark className="h-5 w-auto text-accent group-hover:drop-shadow-[0_0_8px_rgba(16,185,129,0.6)] transition" />
          <span className="font-mono tracking-[0.18em] text-[0.6rem] uppercase text-ink-mute group-hover:text-ink-dim transition">
            observatory
          </span>
        </Link>
      </div>

      <nav className="flex-1 px-3 py-4 overflow-y-auto">
        {user ? (
          <SidebarNav />
        ) : (
          <div className="px-3 py-2 font-mono text-[0.62rem] uppercase tracking-[0.22em] text-ink-mute">
            sign in to continue
          </div>
        )}
      </nav>

      {user ? (
        <div className="px-4 py-4 border-t border-hair/40 flex flex-col gap-3 shrink-0">
          <Link
            href="/settings"
            className="flex items-center gap-2 text-xs font-mono text-ink-mute hover:text-accent min-w-0 transition"
          >
            <span
              className="inline-block w-1.5 h-1.5 rounded-full bg-accent pulse-dot-emerald shrink-0"
              aria-hidden
            />
            <span className="truncate">{user.github_login}</span>
          </Link>
          <div className="text-xs font-mono">
            <SignOutButton />
          </div>
        </div>
      ) : null}
    </aside>
  );
}
