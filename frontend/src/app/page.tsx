import { redirect } from "next/navigation";
import { apiServer } from "@/lib/api-server";
import { loginHref } from "@/lib/api";
import type { User } from "@/lib/types";
import { HeroGraph } from "@/components/HeroGraph";

async function getUser(): Promise<User | null> {
  try {
    return await apiServer<User>("/auth/me");
  } catch {
    return null;
  }
}

export default async function LandingPage() {
  const user = await getUser();
  if (user) redirect("/runs");

  return (
    <div className="relative overflow-hidden min-h-[calc(100vh-3rem)]">
<div className="relative min-h-[calc(100vh-3rem)] flex items-center justify-center">
  <div className="hero-box glass card-inset p-8 rounded-xl max-w-[1100px] mx-auto">
    {/* Hero content moved here */}
    <div className="grid lg:grid-cols-[1.1fr_0.9fr] gap-12 items-center min-h-[60vh]">
      {/* Existing inner content remains unchanged */}
    </div>
  </div>
</div>
        <div className="grid lg:grid-cols-[1.1fr_0.9fr] gap-12 items-center min-h-[60vh]">
          <div className="reveal flex flex-col gap-6">
            <div className="flex items-center gap-3 text-[0.65rem] font-mono uppercase tracking-[0.22em] text-ink-mute">
              <span className="flex items-center gap-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent pulse-dot-emerald" />
                v0.1 / preview
              </span>
              <span className="text-hair-bright">·</span>
              <span>js / ts only</span>
            </div>

            <h1 className="font-mono text-4xl md:text-5xl font-bold leading-[1.08] tracking-tight">
              <span className="text-ink">BloodHound</span>
              <br />
              <span className="text-ink-mute">for the </span>
              <span className="bg-gradient-to-r from-accent via-emerald-300 to-cyan-400 bg-clip-text text-transparent text-glow-accent">
                JavaScript
              </span>
              <br />
              <span className="text-ink-mute">attack surface.</span>
            </h1>

            <p className="text-ink-dim text-sm leading-relaxed max-w-lg">
              Paste a URL, or upload a{" "}
              <code className="font-mono text-accent bg-accent/8 px-1.5 py-0.5 rounded border border-accent/20 text-[0.82rem]">
                .zip
              </code>
              . ASTRA crawls, reconstructs sources from sourcemaps, builds a
              framework-aware callgraph with taint tags, captures runtime
              coverage, and serves it as an interactive graph you query in
              Cypher — or natural language.
            </p>

            <div className="flex items-center gap-4 pt-1">
              <a
                href={loginHref()}
                className="btn-primary"
              >
                <GhIcon className="w-4 h-4" />
                sign in with github
              </a>
              <span className="font-mono text-[0.65rem] uppercase tracking-wider text-ink-mute">
                <kbd className="border border-hair bg-elev/40 px-1.5 py-0.5 rounded text-ink-dim text-[0.6rem]">
                  oauth
                </kbd>{" "}
                · no install
              </span>
            </div>

            <div className="grid grid-cols-3 gap-5 pt-6 mt-1 border-t border-hair/30 max-w-sm">
              <Stat label="ast engine" value="swc" />
              <Stat label="graph db" value="kuzu" />
              <Stat label="advisor" value="sonnet→opus" />
            </div>
          </div>

          <div className="reveal" style={{ animationDelay: "100ms" }}>
            <div className="relative rounded-xl bg-panel/50 card-inset overflow-hidden scanline">
              <div className="absolute inset-0 bg-grid-fine opacity-40" />
              <div className="relative p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-rose-500/70" />
                    <span className="w-2 h-2 rounded-full bg-amber-500/70" />
                    <span className="w-2 h-2 rounded-full bg-emerald-500/70" />
                  </div>
                  <span className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute">
                    callgraph · runtime overlay
                  </span>
                </div>
                <HeroGraph className="w-full h-[280px]" />
                <div className="mt-3 flex items-center justify-between font-mono text-[0.65rem] text-ink-mute">
                  <span className="flex items-center gap-3">
                    <Legend color="#10b981" label="function" />
                    <Legend color="#06b6d4" label="async edge" />
                    <Legend color="#f43f5e" label="sink" />
                  </span>
                  <span className="tabular-nums">10 / 12</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-16 grid md:grid-cols-4 gap-2.5 reveal" style={{ animationDelay: "200ms" }}>
          <Pillar num="01" title="acquisition" desc="Playwright + DevTools fetches every script, dynamic import, blob, sourcemap." />
          <Pillar num="02" title="callgraph" desc="swc AST · framework-aware · async resolver · jsluice-merged taint." />
          <Pillar num="03" title="coverage" desc="Profiler.takePreciseCoverage joined per feature run. Dead vs live." />
          <Pillar num="04" title="query" desc="Raw Cypher, NL prompt, or canned playbooks. Table or subgraph." />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 glass card-inset">
      <span className="font-mono text-[0.55rem] uppercase tracking-[0.22em] text-ink-mute">{label}</span>
      <span className="font-mono text-xs text-ink-dim">{value}</span>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />
      {label}
    </span>
  );
}

function Pillar({ num, title, desc }: { num: string; title: string; desc: string }) {
  return (
    <div className="rounded-lg bg-panel/40 card-sharp p-4 group transition-colors">
      <div className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute mb-2">
        pillar · {num}
      </div>
      <h3 className="font-mono text-xs uppercase tracking-wider text-accent mb-1.5 group-hover:text-glow-accent transition">
        {title}
      </h3>
      <p className="text-ink-dim text-[0.78rem] leading-relaxed">{desc}</p>
    </div>
  );
}

function GhIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.475 2 2 6.475 2 12c0 4.425 2.862 8.162 6.838 9.488.5.087.687-.213.687-.476 0-.237-.013-1.024-.013-1.862-2.512.463-3.162-.613-3.362-1.175-.113-.288-.6-1.175-1.025-1.413-.35-.187-.85-.65-.013-.662.788-.013 1.35.725 1.538 1.025.9 1.512 2.337 1.087 2.912.825.088-.65.35-1.087.638-1.337-2.225-.25-4.55-1.113-4.55-4.938 0-1.088.387-1.987 1.025-2.688-.1-.25-.45-1.275.1-2.65 0 0 .837-.262 2.75 1.026a9.28 9.28 0 0 1 2.5-.338c.85 0 1.7.112 2.5.337 1.912-1.3 2.75-1.024 2.75-1.024.55 1.375.2 2.4.1 2.65.637.7 1.025 1.587 1.025 2.687 0 3.838-2.337 4.688-4.562 4.938.362.312.675.912.675 1.85 0 1.337-.013 2.412-.013 2.75 0 .262.188.574.688.474A10.016 10.016 0 0 0 22 12c0-5.525-4.475-10-10-10z" />
    </svg>
  );
}
