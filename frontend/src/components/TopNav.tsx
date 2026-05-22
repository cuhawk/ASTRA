import Link from "next/link";
import { apiServer } from "@/lib/api-server";
import type { User } from "@/lib/types";
import { SignOutButton } from "./SignOutButton";

async function getUser(): Promise<User | null> {
  try {
    return await apiServer<User>("/auth/me");
  } catch {
    return null;
  }
}

export async function TopNav() {
  const user = await getUser();
  return (
    <nav className="border-b border-zinc-800 bg-zinc-950">
      <div className="max-w-[960px] mx-auto px-6 py-4 flex items-center justify-between">
        <Link
          href="/"
          className="text-emerald-400 font-bold tracking-wider text-lg"
        >
          ASTRA
        </Link>
        {user ? (
          <div className="flex items-center gap-4 text-sm">
            <span className="text-zinc-400">{user.github_login}</span>
            <SignOutButton />
          </div>
        ) : null}
      </div>
    </nav>
  );
}
