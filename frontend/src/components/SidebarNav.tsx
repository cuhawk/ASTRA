"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface Item {
  href: string;
  label: string;
  match: (path: string) => boolean;
}

const ITEMS: Item[] = [
  {
    href: "/runs",
    label: "Runs",
    match: (p) => p === "/runs" || (p.startsWith("/runs/") && p !== "/runs/new"),
  },
  {
    href: "/runs/new",
    label: "New run",
    match: (p) => p === "/runs/new",
  },
  {
    href: "/settings",
    label: "Settings",
    match: (p) => p === "/settings" || p.startsWith("/settings/"),
  },
];

export function SidebarNav() {
  const pathname = usePathname() ?? "";
  return (
    <ul className="flex flex-col gap-0.5">
      {ITEMS.map((item) => {
        const active = item.match(pathname);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={
                "block px-3 py-2 rounded-md font-mono text-xs uppercase tracking-wider transition-colors " +
                (active
                  ? "bg-accent/10 text-accent border border-accent/30"
                  : "text-ink-mute hover:text-ink-dim hover:bg-elev/40 border border-transparent")
              }
            >
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
