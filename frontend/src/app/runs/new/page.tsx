"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { API_BASE } from "@/lib/env";
import { Button } from "@/components/Button";
import type { Run, User } from "@/lib/types";

type Diag = { ok: boolean; status?: number; body: string; url: string; method: string; ts: string };

export default function NewRunPage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<Diag | null>(null);
  const [probe, setProbe] = useState<Diag | null>(null);
  const [probing, setProbing] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = url.trim();
    if (!trimmed) {
      setError({ ok: false, body: "url is empty", url: `${API_BASE}/runs`, method: "POST", ts: new Date().toISOString() });
      return;
    }
    if (!/^https?:\/\//i.test(trimmed)) {
      setError({ ok: false, body: "url must start with http:// or https://", url: `${API_BASE}/runs`, method: "POST", ts: new Date().toISOString() });
      return;
    }
    setSubmitting(true);
    try {
      const run = await api<Run>("/runs", { method: "POST", body: JSON.stringify({ url }) });
      router.push(`/runs/${run.id}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const m = msg.match(/^(\d{3}):\s*([\s\S]*)$/);
      setError({ ok: false, status: m ? Number(m[1]) : undefined, body: m ? m[2] : msg, url: `${API_BASE}/runs`, method: "POST", ts: new Date().toISOString() });
      setSubmitting(false);
    }
  }

  async function testConnection() {
    setProbe(null);
    setProbing(true);
    try {
      const me = await api<User>("/auth/me");
      setProbe({ ok: true, status: 200, body: JSON.stringify(me, null, 2), url: `${API_BASE}/auth/me`, method: "GET", ts: new Date().toISOString() });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const m = msg.match(/^(\d{3}):\s*([\s\S]*)$/);
      setProbe({ ok: false, status: m ? Number(m[1]) : undefined, body: m ? m[2] : msg, url: `${API_BASE}/auth/me`, method: "GET", ts: new Date().toISOString() });
    } finally {
      setProbing(false);
    }
  }

  return (
    <div className="max-w-[800px] mx-auto px-5 py-8 flex flex-col gap-6 reveal">
      <header className="flex flex-col gap-1.5">
        <span className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute">
          new run · acquire → ast → callgraph → taint
        </span>
        <h1 className="text-2xl font-semibold tracking-tight font-mono">
          Point ASTRA at a target<span className="text-ink-mute">.</span>
        </h1>
      </header>

      <div className="rounded-lg bg-panel/50 card-sharp p-5">
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="font-mono text-[0.58rem] uppercase tracking-[0.24em] text-ink-mute">target url</span>
            <div className="relative">
              <span aria-hidden className="absolute left-3 top-1/2 -translate-y-1/2 font-mono text-xs text-ink-mute">→</span>
              <input
                type="text"
                inputMode="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com"
                autoFocus
                className="w-full bg-void/60 border border-hair/80 rounded-md pl-8 pr-3 py-2.5 font-mono text-sm text-ink placeholder:text-ink-mute focus-phosphor transition"
              />
            </div>
          </label>

          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" size="md" disabled={submitting}>
              {submitting ? (
                <><span className="inline-block w-3 h-3 border-2 border-void/40 border-t-void rounded-full orbit" /> submitting</>
              ) : (
                <>analyze <span aria-hidden>↗</span></>
              )}
            </Button>
            <Button type="button" variant="ghost" size="md" onClick={testConnection} disabled={probing}>
              {probing ? "probing" : "test connection"}
            </Button>
          </div>
        </form>
      </div>

      {error ? <DiagBanner kind="error" diag={error} /> : null}
      {probe ? <DiagBanner kind={probe.ok ? "ok" : "error"} diag={probe} title={probe.ok ? "connection ok" : "connection failed"} /> : null}
    </div>
  );
}

function DiagBanner({ kind, diag, title }: { kind: "ok" | "error"; diag: Diag; title?: string }) {
  const isErr = kind === "error";
  const ring = isErr ? "border-rose-700/50" : "border-emerald-700/50";
  const text = isErr ? "text-rose-300" : "text-emerald-300";
  const bg = isErr ? "bg-rose-950/20" : "bg-emerald-950/15";
  const heading = title ?? `request failed${diag.status ? ` · ${diag.status}` : ""}`;
  return (
    <div className={`rounded-lg border ${ring} ${bg} overflow-hidden`} role={isErr ? "alert" : "status"}>
      <div className={`flex items-center justify-between px-4 py-2.5 border-b border-current/20 ${text}`}>
        <div className="flex items-center gap-2.5 font-mono text-[0.65rem] uppercase tracking-[0.18em]">
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${isErr ? "bg-rose-400" : "bg-emerald-400"}`} />
          {heading}
        </div>
        <span className="font-mono text-[0.6rem] uppercase tracking-wider opacity-60">{diag.ts}</span>
      </div>
      <div className="px-4 py-3 space-y-2.5">
        <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 font-mono text-[0.68rem]">
          <span className="text-ink-mute">method</span><span className={text}>{diag.method}</span>
          <span className="text-ink-mute">url</span><span className="text-ink-dim break-all">{diag.url}</span>
          {diag.status ? <><span className="text-ink-mute">status</span><span className={text}>{diag.status}</span></> : null}
        </div>
        <pre className={`font-mono text-xs leading-relaxed bg-void/50 border border-hair/40 rounded-md p-2.5 whitespace-pre-wrap break-words max-h-60 overflow-auto ${text}`}>
          {diag.body || "(empty body)"}
        </pre>
      </div>
    </div>
  );
}
