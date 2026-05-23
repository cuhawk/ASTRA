"use client";

import Link from "next/link";
import { Wordmark } from "./Wordmark";

interface Props {
  threatLevel?: "low" | "moderate" | "high";
  scanStatus?: "idle" | "active" | "done" | "failed";
  children: React.ReactNode;
}

const RAIL_ITEMS: { id: string; href: string; icon: React.ReactNode; label: string; active?: boolean }[] = [
  {
    id: "files",
    href: "#",
    label: "Files",
    active: true,
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
        <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />
      </svg>
    ),
  },
  {
    id: "graph",
    href: "#",
    label: "Graph",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
        <circle cx="6" cy="6" r="2" />
        <circle cx="18" cy="6" r="2" />
        <circle cx="12" cy="18" r="2" />
        <path d="M7.5 7.5 11 16M16.5 7.5 13 16" />
      </svg>
    ),
  },
  {
    id: "settings",
    href: "/settings",
    label: "Settings",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
      </svg>
    ),
  },
];

function ThreatPill({ level }: { level: NonNullable<Props["threatLevel"]> }) {
  const tone = {
    low: "text-emerald-300 bg-emerald-950/40 border-emerald-700/40",
    moderate: "text-amber-300 bg-amber-950/40 border-amber-700/40",
    high: "text-rose-300 bg-rose-950/40 border-rose-700/40",
  }[level];
  return (
    <span
      className={`font-mono text-[0.6rem] uppercase tracking-[0.22em] px-2.5 py-1 rounded border ${tone}`}
    >
      Threat Level: <span className="font-semibold">{level}</span>
    </span>
  );
}

function ScanPill({ status }: { status: NonNullable<Props["scanStatus"]> }) {
  const map = {
    idle: { tone: "text-ink-mute bg-void/60 border-hair/60", label: "idle", dot: "bg-ink-mute" },
    active: { tone: "text-cyan-300 bg-cyan-950/30 border-cyan-700/40", label: "active", dot: "bg-cyan-400" },
    done: { tone: "text-emerald-300 bg-emerald-950/30 border-emerald-700/40", label: "done", dot: "bg-emerald-400" },
    failed: { tone: "text-rose-300 bg-rose-950/30 border-rose-700/40", label: "failed", dot: "bg-rose-400" },
  }[status];
  return (
    <span
      className={`font-mono text-[0.6rem] uppercase tracking-[0.22em] px-2.5 py-1 rounded border inline-flex items-center gap-2 ${map.tone}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${map.dot} pulse-dot-emerald`} aria-hidden />
      Scan Status: <span className="font-semibold">{map.label}</span>
    </span>
  );
}

export function WorkspaceChrome({ threatLevel = "moderate", scanStatus = "active", children }: Props) {
  return (
    <div className="fixed inset-0 z-40 flex flex-col bg-void text-ink overflow-hidden">
      {/* Top bar */}
      <header className="flex items-center justify-between gap-4 px-5 h-14 border-b border-hair/60 bg-void/95 backdrop-blur-md shrink-0 z-20">
        <Link
          href="/"
          className="flex items-center gap-2.5 group shrink-0"
          aria-label="ASTRA home"
        >
          <Wordmark className="h-5 w-auto text-accent group-hover:drop-shadow-[0_0_8px_rgba(16,185,129,0.6)] transition" />
        </Link>

        <div className="hidden md:flex items-center gap-2">
          <ScanPill status={scanStatus} />
          <ThreatPill level={threatLevel} />
        </div>

        <div className="flex items-center gap-1">
          <IconBtn label="Notifications">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
              <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
              <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
            </svg>
          </IconBtn>
          <IconBtn label="Account">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
              <circle cx="12" cy="8" r="4" />
              <path d="M4 21a8 8 0 0 1 16 0" />
            </svg>
          </IconBtn>
          <IconBtn label="Settings" href="/settings">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
            </svg>
          </IconBtn>
        </div>
      </header>

      <div className="flex-1 flex min-h-0">
        {/* Left icon rail */}
        <nav className="w-12 border-r border-hair/60 bg-void/85 flex flex-col items-center py-3 gap-1 shrink-0">
          {RAIL_ITEMS.map((it) => (
            <Link
              key={it.id}
              href={it.href}
              title={it.label}
              className={`w-9 h-9 rounded-md flex items-center justify-center transition border ${
                it.active
                  ? "bg-accent/10 border-accent/40 text-accent shadow-[0_0_12px_rgba(16,185,129,0.18)]"
                  : "border-transparent text-ink-mute hover:text-accent hover:border-hair/60 hover:bg-elev/50"
              }`}
            >
              {it.icon}
            </Link>
          ))}
          <div className="mt-auto">
            <IconBtn label="Help">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                <circle cx="12" cy="12" r="9" />
                <path d="M9.1 9a3 3 0 1 1 5.8 1c0 2-3 2-3 4M12 17h.01" />
              </svg>
            </IconBtn>
          </div>
        </nav>

        {/* Workspace content */}
        <div className="flex-1 min-w-0 min-h-0 overflow-hidden">{children}</div>
      </div>
    </div>
  );
}

function IconBtn({
  children,
  label,
  href,
}: {
  children: React.ReactNode;
  label: string;
  href?: string;
}) {
  const cls =
    "w-9 h-9 rounded-md flex items-center justify-center text-ink-mute hover:text-accent hover:bg-elev/50 transition border border-transparent hover:border-hair/60";
  if (href) {
    return (
      <Link href={href} title={label} aria-label={label} className={cls}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" title={label} aria-label={label} className={cls}>
      {children}
    </button>
  );
}
