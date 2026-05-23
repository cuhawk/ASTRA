"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { GraphViewer } from "@/components/GraphViewer";
import { StatusBadge } from "@/components/StatusBadge";
import type { Run } from "@/lib/types";

const TERMINAL: Run["status"][] = ["done", "failed"];

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      try {
        const r = await api<Run>(`/runs/${id}`);
        if (cancelled) return;
        setRun(r);
        if (!TERMINAL.includes(r.status)) {
          timer = setTimeout(tick, 2000);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      }
    }
    tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  if (error) {
    return (
      <div className="h-screen flex flex-col">
        <RunBar runId={id} />
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-xl w-full rounded-lg border border-rose-700/50 bg-rose-950/20 p-5 text-rose-300 font-mono text-sm whitespace-pre-wrap">
            {error}
          </div>
        </div>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="h-screen flex flex-col">
        <RunBar runId={id} />
        <div className="flex-1 flex items-center justify-center gap-3 text-ink-mute font-mono text-sm">
          <span className="inline-block w-3 h-3 border-2 border-accent border-t-transparent rounded-full orbit" />
          loading run…
        </div>
      </div>
    );
  }

  const inProgress = !TERMINAL.includes(run.status);

  return (
    <div className="h-screen flex flex-col min-h-0">
      <RunBar runId={run.id} status={run.status} url={run.url} files={run.files} functions={run.functions} edges={run.edges} />

      {inProgress ? (
        <div className="flex-1 flex items-center justify-center gap-3 text-ink-dim font-mono text-sm">
          <span className="inline-block w-3 h-3 border-2 border-amber-400 border-t-transparent rounded-full orbit" />
          pipeline <span className="text-amber-300">{run.status}</span> · polling every 2s
        </div>
      ) : run.status === "failed" && run.error ? (
        <div className="flex-1 overflow-auto p-4">
          <div className="rounded-lg border border-rose-700/50 bg-rose-950/20">
            <div className="px-4 py-2.5 border-b border-rose-700/30 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-rose-300">pipeline failed</div>
            <pre className="px-4 py-3 font-mono text-xs text-rose-200 whitespace-pre-wrap break-words">{run.error}</pre>
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0">
          <GraphViewer runId={run.id} />
        </div>
      )}
    </div>
  );
}

function RunBar({
  runId,
  status,
  url,
  files,
  functions,
  edges,
}: {
  runId: string;
  status?: string;
  url?: string | null;
  files?: number;
  functions?: number;
  edges?: number;
}) {
  return (
    <div className="flex items-center gap-3 pl-12 md:pl-4 pr-4 py-2 border-b border-hair/40 bg-panel shrink-0 overflow-x-auto">
      <Link href="/runs" className="font-mono text-[0.6rem] uppercase tracking-[0.2em] text-ink-mute hover:text-accent shrink-0">
        ← runs
      </Link>
      <span className="w-px h-4 bg-hair/40" />
      <span className="font-mono text-[0.72rem] text-accent shrink-0">{runId.slice(0, 12)}</span>
      {status ? (
        <>
          <span className="w-px h-4 bg-hair/40" />
          <StatusBadge status={status} />
        </>
      ) : null}
      {url ? (
        <>
          <span className="w-px h-4 bg-hair/40" />
          <span className="font-mono text-[0.68rem] text-ink-mute truncate max-w-xs" title={url}>{url}</span>
        </>
      ) : null}
      <div className="ml-auto flex items-center gap-3 shrink-0">
        {files !== undefined ? <Chip label="files" value={files} /> : null}
        {functions !== undefined ? <Chip label="funcs" value={functions} /> : null}
        {edges !== undefined ? <Chip label="edges" value={edges} /> : null}
      </div>
    </div>
  );
}

function Chip({ label, value }: { label: string; value: number }) {
  return (
    <span className="font-mono text-[0.6rem] uppercase tracking-[0.18em] text-ink-mute">
      {label} <span className="text-ink-dim tabular-nums">{value.toLocaleString()}</span>
    </span>
  );
}
