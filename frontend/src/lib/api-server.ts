import { cookies } from "next/headers";
import { api } from "./api";

export async function apiServer<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const cookieHeader = (await cookies())
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");
  return api<T>(path, {
    ...init,
    headers: { ...(init?.headers ?? {}), cookie: cookieHeader },
    cache: "no-store",
  });
}
