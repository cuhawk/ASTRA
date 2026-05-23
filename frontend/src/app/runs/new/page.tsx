"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { API_BASE } from "@/lib/env";
import { Button } from "@/components/Button";
import type { Run, User } from "@/lib/types";

type Diag = {
  ok: boolean;
  status?: number;
  body: string;
  url: string;
  method: string;
  ts: string;
};

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
      setError({
        ok: false,
        body: "url is empty",
        url: `${API_BASE}/runs`,
        method: "POST",
        ts: new Date().toISOString(),
      });
      return;
    }
    if (!/^https?:\/\//i.test(trimmed)) {
      setError({
        ok: false,
        body: "url must start with http:// or https://",
        url: `${API_BASE}/runs`,
        method: "POST",
        ts: new Date().toISOString(),
      });
      return;
    }
    setSubmitting(true);
    // Surface intent in console for devtools-debuggable failures.
    console.info("[astra] POST /runs", {
      url,
      base: API_BASE,
      now: new Date().toISOString(),
    });
    try {
      const run = await api<Run>("/runs", {
        method: "POST",
        body: JSON.stringify({ url }),
      });
      console.info("[astra] response /runs", run);
      router.push(`/runs/${run.id}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      // api() throws Error("<status>: <body>"); split it back out.
      const m = msg.match(/^(\d{3}):\s*([\s\S]*)$/);
      const diag: Diag = {
        ok: false,
        status: m ? Number(m[1]) : undefined,
        body: m ? m[2] : msg,
        url: `${API_BASE}/runs`,
        method: "POST",
        ts: new Date().toISOString(),
      };
      console.info("[astra] response /runs (error)", diag);
      setError(diag);
      setSubmitting(false);
    }
  }

  async function testConnection() {
    setProbe(null);
    setProbing(true);
    console.info("[astra] GET /auth/me", {
      base: API_BASE,
      now: new Date().toISOString(),
    });
    try {
      const me = await api<User>("/auth/me");
      console.info("[astra] response /auth/me", me);
      setProbe({
        ok: true,
        status: 200,
        body: JSON.stringify(me, null, 2),
        url: `${API_BASE}/auth/me`,
        method: "GET",
        ts: new Date().toISOString(),
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const m = msg.match(/^(\d{3}):\s*([\s\S]*)$/);
      const diag: Diag = {
        ok: false,
        status: m ? Number(m[1]) : undefined,
        body: m ? m[2] : msg,
        url: `${API_BASE}/auth/me`,
        method: "GET",
        ts: new Date().toISOString(),
      };
      console.info("[astra] response /auth/me (error)", diag);
      setProbe(diag);
    } finally {
      setProbing(false);
    }
  }

  return (
    <div className="max-w-[860px] mx-auto px-6 py-12 flex flex-col gap-8 reveal">
      <header className="flex flex-col gap-2">
        <span className="font-mono text-[0.65rem] uppercase tracking-[0.24em] text-ink-mute">
          new run · acquire → ast → callgraph → taint
        </span>
        <h1 className="text-3xl font-semibold tracking-tight">
          Point ASTRA at a target<span className="text-ink-mute">.</span>
        </h1>
      </header>

      <div className="rounded-lg bg-panel/60 card-inset p-6">
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
          <label className="flex flex-col gap-2">
            <span className="font-mono text-[0.62rem] uppercase tracking-[0.24em] text-ink-mute">
              target url
            </span>
            <div className="relative">
              <span
                aria-hidden
                className="absolute left-3 top-1/2 -translate-y-1/2 font-mono text-xs text-ink-mute"
              >
                →
              </span>
              <input
                type="text"
                inputMode="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com"
                autoFocus
                className="w-full bg-void/60 border border-hair rounded-md pl-8 pr-3 py-2.5 font-mono text-sm text-ink placeholder:text-ink-mute focus-phosphor transition"
              />
            </div>
          </label>

          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" size="lg" disabled={submitting}>
              {submitting ? (
                <>
                  <span className="inline-block w-3 h-3 border-2 border-void/40 border-t-void rounded-full orbit" />
                  submitting
                </>
              ) : (
                <>
                  <span>analyze</span>
                  <span aria-hidden>↗</span>
                </>
              )}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="lg"
              onClick={testConnection}
              disabled={probing}
            >
              {probing ? "probing" : "test connection"}
            </Button>
            <span className="font-mono text-[0.7rem] uppercase tracking-wider text-ink-mute ml-auto">
              POST {API_BASE}/runs
            </span>
          </div>

          <p className="font-mono text-[0.72rem] text-ink-mute leading-relaxed">
            If submit hangs or 401s, check DevTools → Network. Backend at{" "}
            <code className="text-ink-dim">http://127.0.0.1:8000</code>. The
            session cookie is set by{" "}
            <code className="text-ink-dim">/auth/github/callback</code> on the
            backend host — if you opened the frontend at{" "}
            <code className="text-ink-dim">localhost:3000</code> instead of{" "}
            <code className="text-ink-dim">127.0.0.1:3000</code>, the cookie
            won&apos;t flow (different SameSite scope).
          </p>
        </form>
      </div>

      {error ? <DiagBanner kind="error" diag={error} /> : null}
      {probe ? (
        <DiagBanner
          kind={probe.ok ? "ok" : "error"}
          diag={probe}
          title={probe.ok ? "connection ok" : "connection failed"}
        />
      ) : null}
    </div>
  );
}

function DiagBanner({
  kind,
  diag,
  title,
}: {
  kind: "ok" | "error";
  diag: Diag;
  title?: string;
}) {
  const isErr = kind === "error";
  const ring = isErr ? "border-rose-700/60" : "border-emerald-700/60";
  const text = isErr ? "text-rose-300" : "text-emerald-300";
  const bg = isErr ? "bg-rose-950/30" : "bg-emerald-950/20";
  const heading = title ?? `request failed${diag.status ? ` · ${diag.status}` : ""}`;
  return (
    <div
      className={`rounded-lg border ${ring} ${bg} overflow-hidden`}
      role={isErr ? "alert" : "status"}
    >
      <div
        className={`flex items-center justify-between px-5 py-3 border-b border-current/20 ${text}`}
      >
        <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.18em]">
          <span
            className={`inline-block w-2 h-2 rounded-full ${
              isErr ? "bg-rose-400" : "bg-emerald-400"
            }`}
          />
          {heading}
        </div>
        <span className="font-mono text-[0.65rem] uppercase tracking-wider opacity-70">
          {diag.ts}
        </span>
      </div>
      <div className="px-5 py-4 space-y-3">
        <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 font-mono text-[0.72rem]">
          <span className="text-ink-mute">method</span>
          <span className={text}>{diag.method}</span>
          <span className="text-ink-mute">url</span>
          <span className="text-ink-dim break-all">{diag.url}</span>
          {diag.status ? (
            <>
              <span className="text-ink-mute">status</span>
              <span className={text}>{diag.status}</span>
            </>
          ) : null}
        </div>
        <pre
          className={`font-mono text-xs leading-relaxed bg-void/60 border border-hair rounded-md p-3 whitespace-pre-wrap break-words max-h-72 overflow-auto ${text}`}
        >
          {diag.body || "(empty body)"}
        </pre>
      </div>
    </div>
  );
}
