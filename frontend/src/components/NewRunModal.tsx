"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/Button";
import type { Run } from "@/lib/types";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function NewRunModal({ open, onClose }: Props) {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = url.trim();
    if (!trimmed) { setError("url is empty"); return; }
    if (!/^https?:\/\//i.test(trimmed)) { setError("url must start with http:// or https://"); return; }
    setSubmitting(true);
    try {
      const run = await api<Run>("/runs", { method: "POST", body: JSON.stringify({ url }) });
      setUrl("");
      setError(null);
      onClose();
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-void/80 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-lg mx-4 rounded-lg bg-panel card-sharp border border-hair/60 overflow-hidden reveal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-hair/40">
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute">
            new run · acquire → ast → callgraph → taint
          </span>
          <button
            type="button"
            onClick={onClose}
            className="w-6 h-6 rounded flex items-center justify-center text-ink-mute hover:text-ink hover:bg-elev/50 transition"
          >
            ×
          </button>
        </div>

        <form onSubmit={onSubmit} noValidate className="p-5 flex flex-col gap-4">
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

          {error ? (
            <div className="rounded-md border border-rose-700/50 bg-rose-950/20 text-rose-300 font-mono text-xs p-2.5 whitespace-pre-wrap break-words">
              {error}
            </div>
          ) : null}

          <div className="flex items-center gap-3">
            <Button type="submit" size="md" disabled={submitting}>
              {submitting ? (
                <><span className="inline-block w-3 h-3 border-2 border-void/40 border-t-void rounded-full orbit" /> submitting</>
              ) : (
                <>analyze <span aria-hidden>↗</span></>
              )}
            </Button>
            <Button type="button" variant="ghost" size="md" onClick={onClose}>
              cancel
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
