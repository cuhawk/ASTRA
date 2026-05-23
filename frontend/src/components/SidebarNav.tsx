"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  match: (p: string) => boolean;
}

const ITEMS: NavItem[] = [
  {
    href: "/runs",
    label: "Runs",
    match: (p) => p === "/runs" || (p.startsWith("/runs/") && p !== "/runs/new"),
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 shrink-0">
        <circle cx="6" cy="6" r="2" />
        <circle cx="18" cy="6" r="2" />
        <circle cx="12" cy="18" r="2" />
        <path d="M7.5 7.5 11 16M16.5 7.5 13 16" />
      </svg>
    ),
  },
  {
    href: "/settings",
    label: "Settings",
    match: (p) => p === "/settings" || p.startsWith("/settings/"),
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 shrink-0">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
      </svg>
    ),
  },
];

export function SidebarNav({ collapsed = true }: { collapsed?: boolean }) {
  const pathname = usePathname() ?? "";
  return (
    <div className={`flex flex-col gap-1 ${collapsed ? "items-center" : "w-full"}`}>
      {ITEMS.map((item) => {
        const active = item.match(pathname);
        return (
          <Link
            key={item.href}
            href={item.href}
            title={collapsed ? item.label : undefined}
            aria-label={item.label}
            aria-current={active ? "page" : undefined}
            className={`rounded-md flex items-center transition border ${
              active
                ? "bg-accent/10 border-accent/40 text-accent shadow-[0_0_12px_rgba(16,185,129,0.15)]"
                : "border-transparent text-ink-mute hover:text-accent hover:border-hair/50 hover:bg-elev/40"
            } ${
              collapsed
                ? "w-9 h-9 justify-center"
                : "w-full h-9 gap-2.5 px-2.5"
            }`}
          >
            {item.icon}
            {!collapsed && (
              <span className="font-mono text-[0.62rem] uppercase tracking-[0.18em]">
                {item.label}
              </span>
            )}
          </Link>
        );
      })}
    </div>
  );
}
