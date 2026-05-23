"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { humanizeAge } from "@/lib/format";
import type { VaultStatus } from "@/lib/types";

const PROVIDER = "anthropic";

interface Props {
  initial: VaultStatus;
}

export function AnthropicKeyCard({ initial }: Props) {
  const [status, setStatus] = useState<VaultStatus>(initial);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    setStatus(initial);
  }, [initial]);

  async function save() {
    const trimmed = input.trim();
    if (!trimmed) return;
    setError(null);
    setMsg(null);
    setSaving(true);
    try {
      const next = await api<VaultStatus>(`/vault/keys/${PROVIDER}`, {
        method: "PUT",
        body: JSON.stringify({ key: trimmed }),
      });
      setStatus(next);
      setInput("");
      setMsg("Key saved. Pro-tier LLM calls now route through your Anthropic key.");
    } catch (err) {
      setError(humanizeError(err));
    } finally {
      setSaving(false);
    }
  }

  async function doDelete() {
    setError(null);
    setMsg(null);
    setDeleting(true);
    try {
      await api<void>(`/vault/keys/${PROVIDER}`, { method: "DELETE" });
      setStatus({ provider: PROVIDER, present: false, updated_at: null });
      setConfirmDelete(false);
      setMsg("Key removed. Reverted to free-tier Gemini.");
    } catch (err) {
      setError(humanizeError(err));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="rounded-lg bg-panel/60 card-inset p-6 flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute">
          anthropic api key
        </span>
        <Badge present={status.present} />
      </div>

      <p className="text-ink-dim text-sm leading-relaxed">
        Optional. Paste an Anthropic API key to unlock the Pro tier (Sonnet →
        Opus cascade for advisor calls). Without it, ASTRA stays on free-tier
        Gemini with a 100 calls/day quota. Stored AES-GCM encrypted at rest.
      </p>

      <div className="flex flex-col gap-2">
        <label className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute">
          paste key
        </label>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="password"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="sk-ant-…"
            spellCheck={false}
            autoComplete="off"
            className="flex-1 bg-void/60 border border-hair/60 rounded-md px-3 py-2 font-mono text-sm text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/40"
          />
          <button
            type="button"
            onClick={save}
            disabled={saving || !input.trim()}
            className="bg-accent text-void px-5 py-2 rounded-md font-mono text-xs uppercase tracking-wider hover:bg-accent/90 active:translate-y-px transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "saving…" : status.present ? "replace" : "save"}
          </button>
        </div>
      </div>

      {status.present ? (
        <div className="flex items-center justify-between gap-3 pt-3 border-t border-hair/30">
          <div className="flex flex-col gap-0.5">
            <span className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute">
              stored
            </span>
            <span className="font-mono text-xs text-ink-dim tabular-nums">
              {status.updated_at
                ? `${humanizeAge(status.updated_at)} · ${new Date(status.updated_at * 1000).toLocaleString()}`
                : "—"}
            </span>
          </div>
          {confirmDelete ? (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={doDelete}
                disabled={deleting}
                className="inline-flex items-center border border-rose-500/60 bg-rose-950/40 text-rose-200 hover:bg-rose-900/40 px-3 py-1.5 rounded-md font-mono text-[0.65rem] uppercase tracking-wider transition disabled:opacity-50"
              >
                {deleting ? "removing…" : "confirm remove"}
              </button>
              <button
                type="button"
                onClick={() => setConfirmDelete(false)}
                disabled={deleting}
                className="font-mono text-[0.65rem] uppercase tracking-wider text-ink-mute hover:text-ink-dim px-2 py-1.5"
              >
                cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="inline-flex items-center border border-hair bg-elev/40 hover:border-rose-500/60 hover:text-rose-300 px-3 py-1.5 rounded-md font-mono text-[0.65rem] uppercase tracking-wider text-ink-dim transition"
            >
              remove
            </button>
          )}
        </div>
      ) : null}

      {msg ? (
        <p className="font-mono text-xs text-accent">{msg}</p>
      ) : null}
      {error ? (
        <p className="font-mono text-xs text-rose-300">{error}</p>
      ) : null}
    </div>
  );
}

function Badge({ present }: { present: boolean }) {
  return (
    <span
      className={
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md font-mono text-[0.6rem] uppercase tracking-[0.18em] " +
        (present
          ? "bg-accent/10 border border-accent/40 text-accent"
          : "border border-hair/60 text-ink-mute")
      }
    >
      <span
        className={
          "inline-block w-1.5 h-1.5 rounded-full " +
          (present ? "bg-accent" : "bg-ink-mute")
        }
      />
      {present ? "pro tier" : "not set"}
    </span>
  );
}

function humanizeError(err: unknown): string {
  if (!(err instanceof Error)) return String(err);
  const msg = err.message;
  // The api() helper throws "<status>: <body>". Surface 422 detail cleanly.
  const m = msg.match(/^(\d{3}):\s*(.*)$/s);
  if (!m) return msg;
  const status = m[1];
  const rest = m[2];
  try {
    const parsed = JSON.parse(rest);
    if (parsed?.detail) return `${status}: ${parsed.detail}`;
  } catch {
    /* not JSON */
  }
  return `${status}: ${rest}`;
}
