"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

interface Props {
  runId: string;
  variant?: "row" | "header";
  onDeleted?: () => void;
  redirectTo?: string;
}

export function DeleteRunButton({
  runId,
  variant = "row",
  onDeleted,
  redirectTo,
}: Props) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  async function doDelete() {
    setError(null);
    try {
      await api<void>(`/runs/${runId}`, { method: "DELETE" });
      if (onDeleted) onDeleted();
      if (redirectTo) {
        router.push(redirectTo);
      }
      startTransition(() => router.refresh());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setConfirming(false);
    }
  }

  if (variant === "header") {
    return (
      <div className="flex items-center gap-2">
        {error ? (
          <span className="font-mono text-[0.65rem] text-rose-300">
            {error}
          </span>
        ) : null}
        {confirming ? (
          <>
            <button
              type="button"
              disabled={pending}
              onClick={doDelete}
              className="inline-flex items-center gap-2 border border-rose-500/60 bg-rose-950/40 text-rose-200 hover:bg-rose-900/40 px-4 py-2 rounded-md font-mono text-xs uppercase tracking-wider transition disabled:opacity-50"
            >
              {pending ? "deleting…" : "confirm delete"}
            </button>
            <button
              type="button"
              disabled={pending}
              onClick={() => setConfirming(false)}
              className="font-mono text-xs uppercase tracking-wider text-ink-mute hover:text-ink-dim px-3 py-2"
            >
              cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="inline-flex items-center gap-2 border border-hair bg-elev/40 hover:border-rose-500/60 hover:text-rose-300 px-4 py-2 rounded-md font-mono text-xs uppercase tracking-wider text-ink-dim transition"
          >
            delete
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center justify-end gap-1.5">
      {confirming ? (
        <>
          <button
            type="button"
            disabled={pending}
            onClick={doDelete}
            className="font-mono text-[0.65rem] uppercase tracking-wider text-rose-300 hover:text-rose-200 px-2 py-1 rounded border border-rose-500/40 hover:border-rose-500/70 transition disabled:opacity-50"
          >
            {pending ? "…" : "confirm"}
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={() => setConfirming(false)}
            className="font-mono text-[0.65rem] uppercase tracking-wider text-ink-mute hover:text-ink-dim px-2 py-1"
          >
            cancel
          </button>
        </>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          title="Delete run"
          className="font-mono text-[0.65rem] uppercase tracking-wider text-ink-mute hover:text-rose-300 px-2 py-1 rounded transition opacity-0 group-hover:opacity-100 focus:opacity-100"
        >
          delete
        </button>
      )}
      {error ? (
        <span className="font-mono text-[0.6rem] text-rose-300" title={error}>
          err
        </span>
      ) : null}
    </div>
  );
}
