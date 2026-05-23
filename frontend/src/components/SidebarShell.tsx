"use client";

import { useState } from "react";
import Link from "next/link";
import type { User } from "@/lib/types";
import { SidebarNav } from "./SidebarNav";
import { Wordmark } from "./Wordmark";

interface Props {
  user: User | null;
}

export function SidebarShell({ user }: Props) {
  const [collapsed, setCollapsed] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const w = collapsed ? "w-12" : "w-44";
  const pad = collapsed ? "3rem" : "11rem";

  return (
    <>
      {/* Mobile hamburger */}
      <button
        type="button"
        onClick={() => setMobileOpen(true)}
        aria-label="Open menu"
        className="md:hidden fixed top-3 left-3 z-40 w-9 h-9 rounded-md flex items-center justify-center bg-panel border border-hair/50 text-ink-mute hover:text-accent transition"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="w-4 h-4">
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50" onClick={() => setMobileOpen(false)}>
          <div className="absolute inset-0 bg-void/80 backdrop-blur-sm" />
          <nav
            className="relative w-52 h-full flex flex-col border-r border-hair/50 bg-void/95"
            onClick={(e) => e.stopPropagation()}
          >
            <Link
              href="/"
              onClick={() => setMobileOpen(false)}
              className="flex items-center gap-2.5 h-12 px-3 border-b border-hair/50 shrink-0 group"
              aria-label="ASTRA home"
            >
              <AstraGlyph />
              <Wordmark className="h-4 w-auto text-accent" />
            </Link>
            <div className="flex-1 flex flex-col py-3 px-2 gap-1">
              {user ? <SidebarNav collapsed={false} /> : null}
            </div>
            {user ? (
              <Link
                href="/settings"
                onClick={() => setMobileOpen(false)}
                className="flex items-center gap-2.5 h-9 px-2.5 mx-2 mb-3 rounded-md bg-accent/15 border border-accent/30 text-accent font-mono text-xs font-bold uppercase hover:bg-accent/25 transition"
              >
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-accent/20 shrink-0">
                  {user.github_login.charAt(0)}
                </span>
                <span className="font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-dim truncate">
                  {user.github_login}
                </span>
              </Link>
            ) : null}
          </nav>
        </div>
      )}

      {/* Desktop sidebar */}
      <nav
        className={`hidden md:flex fixed inset-y-0 left-0 z-30 flex-col border-r border-hair/50 bg-void/90 backdrop-blur-md transition-all duration-200 ${w}`}
      >
        {/* Logo */}
        <Link
          href="/"
          className={`flex items-center h-12 border-b border-hair/50 shrink-0 group ${
            collapsed ? "justify-center px-0" : "gap-2.5 px-3"
          }`}
          aria-label="ASTRA home"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="w-5 h-5 text-accent group-hover:drop-shadow-[0_0_8px_rgba(16,185,129,0.6)] transition shrink-0"
          >
            <g stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
              <line x1="6" y1="4" x2="14" y2="12" opacity="0.7" />
              <line x1="14" y1="12" x2="8" y2="20" opacity="0.7" />
            </g>
            <g fill="currentColor">
              <circle cx="6" cy="4" r="2.2" />
              <circle cx="14" cy="12" r="2.8" />
              <circle cx="8" cy="20" r="1.8" opacity="0.8" />
            </g>
          </svg>
          {!collapsed && (
            <Wordmark className="h-4 w-auto text-accent" />
          )}
        </Link>

        {/* Nav items */}
        <div className={`flex-1 flex flex-col py-3 gap-1 ${collapsed ? "items-center" : "px-2"}`}>
          {user ? <SidebarNav collapsed={collapsed} /> : null}
        </div>

        {/* User avatar + collapse toggle */}
        <div className={`flex flex-col gap-2 pb-3 ${collapsed ? "items-center" : "px-2"}`}>
          {/* Collapse toggle */}
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={`rounded-md flex items-center gap-2 text-ink-mute hover:text-accent hover:bg-elev/40 transition ${
              collapsed
                ? "w-9 h-9 justify-center"
                : "w-full h-8 px-2.5"
            }`}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 shrink-0">
              {collapsed ? <path d="M9 18l6-6-6-6" /> : <path d="M15 18l-6-6 6-6" />}
            </svg>
            {!collapsed && (
              <span className="font-mono text-[0.62rem] uppercase tracking-[0.18em]">collapse</span>
            )}
          </button>

          {/* User avatar */}
          {user ? (
            <Link
              href="/settings"
              title={user.github_login}
              className={`rounded-full bg-accent/15 border border-accent/30 text-accent font-mono text-xs font-bold uppercase hover:bg-accent/25 hover:border-accent/50 transition shrink-0 flex items-center ${
                collapsed
                  ? "w-9 h-9 justify-center"
                  : "w-full h-9 gap-2.5 px-2.5 rounded-md"
              }`}
            >
              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-accent/20 shrink-0">
                {user.github_login.charAt(0)}
              </span>
              {!collapsed && (
                <span className="font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-dim truncate">
                  {user.github_login}
                </span>
              )}
            </Link>
          ) : null}
        </div>
      </nav>

      <style>{`@media (min-width: 768px) { main { padding-left: ${pad}; transition: padding-left 200ms; } }`}</style>
    </>
  );
}

function AstraGlyph() {
  return (
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-accent shrink-0">
      <g stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
        <line x1="6" y1="4" x2="14" y2="12" opacity="0.7" />
        <line x1="14" y1="12" x2="8" y2="20" opacity="0.7" />
      </g>
      <g fill="currentColor">
        <circle cx="6" cy="4" r="2.2" />
        <circle cx="14" cy="12" r="2.8" />
        <circle cx="8" cy="20" r="1.8" opacity="0.8" />
      </g>
    </svg>
  );
}
