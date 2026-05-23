import { apiServer } from "@/lib/api-server";
import type { User } from "@/lib/types";
import { SidebarShell } from "./SidebarShell";

async function getUser(): Promise<User | null> {
  try {
    return await apiServer<User>("/auth/me");
  } catch {
    return null;
  }
}

export async function Sidebar() {
  const user = await getUser();
  return <SidebarShell user={user} />;
}
