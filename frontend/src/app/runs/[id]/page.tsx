"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { GraphViewer } from "@/components/GraphViewer";
import { QueryBar } from "@/components/QueryBar";
import { RunChat } from "@/components/RunChat";
import { DeleteRunButton } from "@/components/DeleteRunButton";
import { humanizeAge } from "@/lib/format";
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
      <div className="max-w-[1200px] mx-auto px-6 py-10">
        <div className="rounded-lg border border-rose-700/60 bg-rose-950/30 p-6 text-rose-300 font-mono text-sm whitespace-pre-wrap">
          {error}
        </div>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="max-w-[1200px] mx-auto px-6 py-10 flex items-center gap-3 text-ink-mute font-mono text-sm">
        <span className="inline-block w-3 h-3 border-2 border-accent border-t-transparent rounded-full orbit" />
        loading run…
      </div>
    );
  }

  const inProgress = !TERMINAL.includes(run.status);

  return (
    <div className="max-w-[1200px] mx-auto px-6 py-10 flex flex-col gap-8 reveal">
      <header className="flex flex-col gap-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex flex-col gap-2 min-w-0 flex-1">
            <Link
              href="/runs"
              className="font-mono text-[0.65rem] uppercase tracking-[0.22em] text-ink-mute hover:text-accent w-fit"
            >
              ← all runs
            </Link>
            <h1 className="flex items-center gap-3 flex-wrap">
              <span className="font-mono text-2xl md:text-3xl text-accent tracking-tight break-all">
                {run.id}
              </span>
              <StatusBadge status={run.status} />
            </h1>
            <div className="font-mono text-xs text-ink-mute flex items-center gap-3 flex-wrap">
              <span>created {humanizeAge(run.created_at)}</span>
              {run.finished_at ? (
                <>
                  <span className="text-hair-bright">·</span>
                  <span>finished {humanizeAge(run.finished_at)}</span>
                </>
              ) : null}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {run.status === "done" ? (
              <Link
                href={`/runs/${run.id}/features`}
                className="inline-flex items-center gap-2 border border-hair bg-elev/40 hover:border-accent/60 hover:text-accent px-4 py-2 rounded-md font-mono text-xs uppercase tracking-wider text-ink-dim transition"
              >
                features <span aria-hidden>→</span>
              </Link>
            ) : null}
            <DeleteRunButton
              runId={run.id}
              variant="header"
              redirectTo="/runs"
            />
          </div>
        </div>

        <div className="rounded-lg bg-panel/60 card-inset p-5">
          <div className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute mb-2">
            target
          </div>
          <div className="font-mono text-sm text-ink-dim break-all">
            {run.url ?? "—"}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <Metric label="files" value={run.files} />
          <Metric label="functions" value={run.functions} />
          <Metric label="edges" value={run.edges} />
        </div>
      </header>

      {inProgress ? (
        <div className="rounded-lg bg-panel/60 card-inset px-5 py-4 flex items-center gap-3 text-ink-dim font-mono text-sm">
          <span className="inline-block w-3 h-3 border-2 border-amber-400 border-t-transparent rounded-full orbit" />
          <span>
            pipeline <span className="text-amber-300">{run.status}</span> · polling
            every 2s
          </span>
        </div>
      ) : null}

      {run.status === "failed" && run.error ? (
        <div className="rounded-lg border border-rose-700/60 bg-rose-950/30">
          <div className="px-5 py-3 border-b border-rose-700/40 font-mono text-xs uppercase tracking-[0.18em] text-rose-300">
            pipeline failed
          </div>
          <pre className="px-5 py-4 font-mono text-xs text-rose-200 whitespace-pre-wrap break-words max-h-80 overflow-auto">
            {run.error}
          </pre>
        </div>
      ) : null}

      {run.status === "done" ? (
        <>
          <section className="flex flex-col gap-3">
            <SectionTitle eyebrow="visualization" title="callgraph" />
            <GraphViewer runId={run.id} />
          </section>

          <section className="flex flex-col gap-3">
            <SectionTitle eyebrow="interrogate" title="query" />
            <QueryBar runId={run.id} />
          </section>

          <section className="flex flex-col gap-3">
            <SectionTitle eyebrow="conversation" title="chat" />
            <RunChat runId={run.id} />
          </section>
        </>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-panel/50 card-inset p-5 flex flex-col gap-1.5">
      <span className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute">
        {label}
      </span>
      <span className="font-mono text-3xl text-ink tabular-nums tracking-tight">
        {value.toLocaleString()}
      </span>
    </div>
  );
}

function SectionTitle({
  eyebrow,
  title,
}: {
  eyebrow: string;
  title: string;
}) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="font-mono text-[0.62rem] uppercase tracking-[0.24em] text-ink-mute">
        {eyebrow}
      </span>
      <span className="h-px flex-1 bg-gradient-to-r from-hair via-hair/50 to-transparent" />
      <span className="font-mono text-sm uppercase tracking-[0.18em] text-ink-dim">
        {title}
      </span>
    </div>
  );
}
