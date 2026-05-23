"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface CypherOut {
  cypher: string;
  rows: Record<string, unknown>[];
  row_count: number;
  duration_ms: number;
}

interface NLOut extends CypherOut {
  nl_prompt: string;
}

interface Playbook {
  slug: string;
  name: string;
  description?: string;
  cypher?: string;
  params?: Record<string, unknown>;
}

type Mode = "cypher" | "nl" | "playbook";

export function QueryBar({ runId }: { runId: string }) {
  const [mode, setMode] = useState<Mode>("cypher");
  const [cypher, setCypher] = useState(
    "MATCH (f:Function) RETURN f.name, f.path LIMIT 25",
  );
  const [prompt, setPrompt] = useState("");
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [playbookSlug, setPlaybookSlug] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<CypherOut | NLOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadPlaybooks() {
      try {
        const list = await api<Playbook[]>("/playbooks");
        if (!cancelled) {
          setPlaybooks(list);
          if (list.length && !playbookSlug) setPlaybookSlug(list[0].slug);
        }
      } catch {
        /* non-fatal */
      }
    }
    loadPlaybooks();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function run() {
    setError(null);
    setSubmitting(true);
    setResult(null);
    try {
      if (mode === "cypher") {
        const out = await api<CypherOut>(`/runs/${runId}/cypher`, {
          method: "POST",
          body: JSON.stringify({ query: cypher }),
        });
        setResult(out);
      } else if (mode === "nl") {
        const out = await api<NLOut>(`/runs/${runId}/nl`, {
          method: "POST",
          body: JSON.stringify({ prompt }),
        });
        setResult(out);
      } else {
        if (!playbookSlug) {
          setError("pick a playbook first");
          setSubmitting(false);
          return;
        }
        const out = await api<CypherOut>(
          `/runs/${runId}/playbooks/${playbookSlug}`,
          {
            method: "POST",
            body: JSON.stringify({}),
          },
        );
        setResult(out);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg bg-panel/60 card-inset overflow-hidden">
      <div className="flex items-stretch border-b border-hair/60 bg-elev/30">
        <Tab active={mode === "cypher"} onClick={() => setMode("cypher")}>
          raw cypher
        </Tab>
        <Tab active={mode === "nl"} onClick={() => setMode("nl")}>
          nl prompt
        </Tab>
        <Tab active={mode === "playbook"} onClick={() => setMode("playbook")}>
          playbooks
        </Tab>
        <div className="flex-1" />
        {result ? (
          <div className="flex items-center px-4 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-ink-mute gap-3">
            <span>
              rows{" "}
              <span className="text-ink-dim tabular-nums">
                {result.row_count}
              </span>
            </span>
            <span>
              {result.duration_ms}
              <span className="text-ink-mute">ms</span>
            </span>
          </div>
        ) : null}
      </div>

      <div className="p-4 flex flex-col gap-3">
        {mode === "cypher" ? (
          <textarea
            value={cypher}
            onChange={(e) => setCypher(e.target.value)}
            rows={3}
            className="w-full bg-void/60 border border-hair rounded-md p-3 font-mono text-[0.82rem] text-ink placeholder:text-ink-mute focus-phosphor resize-y"
            placeholder="MATCH (n) RETURN n LIMIT 10"
            spellCheck={false}
          />
        ) : mode === "nl" ? (
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            className="w-full bg-void/60 border border-hair rounded-md p-3 text-sm text-ink placeholder:text-ink-mute focus-phosphor resize-y"
            placeholder="show functions named handleSubmit and what they call"
          />
        ) : (
          <div className="flex flex-col gap-2">
            <select
              value={playbookSlug}
              onChange={(e) => setPlaybookSlug(e.target.value)}
              className="w-full bg-void/60 border border-hair rounded-md p-2.5 font-mono text-sm text-ink focus-phosphor"
            >
              {playbooks.length === 0 ? (
                <option value="">(no playbooks loaded)</option>
              ) : null}
              {playbooks.map((p) => (
                <option key={p.slug} value={p.slug}>
                  {p.slug} — {p.name}
                </option>
              ))}
            </select>
            {playbooks.find((p) => p.slug === playbookSlug)?.description ? (
              <p className="text-xs text-ink-mute">
                {playbooks.find((p) => p.slug === playbookSlug)?.description}
              </p>
            ) : null}
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={run}
            disabled={submitting}
            className="inline-flex items-center gap-2 bg-accent text-void px-4 py-2 rounded-md font-mono text-xs uppercase tracking-wider hover:bg-accent/90 hover:shadow-[0_0_18px_-4px_rgba(16,185,129,0.6)] active:translate-y-px transition-all disabled:opacity-50 disabled:cursor-not-allowed focus-phosphor"
          >
            {submitting ? (
              <>
                <span className="inline-block w-3 h-3 border-2 border-void/40 border-t-void rounded-full orbit" />
                running
              </>
            ) : (
              <>
                <span>execute</span>
                <span aria-hidden>↵</span>
              </>
            )}
          </button>
          {mode === "cypher" ? (
            <span className="font-mono text-[0.65rem] uppercase tracking-wider text-ink-mute">
              read-only · MATCH / RETURN / WHERE
            </span>
          ) : null}
        </div>

        {error ? (
          <div className="rounded-md border border-rose-700/60 bg-rose-950/30 text-rose-300 font-mono text-xs p-3 whitespace-pre-wrap break-words">
            {error}
          </div>
        ) : null}

        {result ? (
          <div className="flex flex-col gap-2">
            {"nl_prompt" in result || mode === "nl" || mode === "playbook" ? (
              <div className="rounded-md border border-hair/60 bg-void/60 p-3">
                <div className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute mb-1">
                  cypher
                </div>
                <pre className="font-mono text-xs text-accent whitespace-pre-wrap break-words">
                  {result.cypher}
                </pre>
              </div>
            ) : null}
            <ResultsTable rows={result.rows} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

function Tab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative px-4 py-3 font-mono text-[0.7rem] uppercase tracking-[0.18em] transition-colors ${
        active
          ? "text-accent"
          : "text-ink-mute hover:text-ink-dim"
      }`}
    >
      {children}
      {active ? (
        <span
          aria-hidden
          className="absolute left-3 right-3 -bottom-px h-[2px] bg-accent shadow-[0_0_10px_rgba(16,185,129,0.7)]"
        />
      ) : null}
    </button>
  );
}

function ResultsTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="rounded-md border border-hair/60 bg-void/40 px-4 py-6 text-center text-ink-mute font-mono text-xs uppercase tracking-wider">
        no rows returned
      </div>
    );
  }
  const cols = Object.keys(rows[0]);
  return (
    <div className="rounded-md border border-hair/60 bg-void/60 overflow-auto max-h-[420px]">
      <table className="w-full text-sm">
        <thead className="bg-elev/40 sticky top-0">
          <tr>
            {cols.map((c) => (
              <th
                key={c}
                className="px-3 py-2.5 text-left font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute border-b border-hair/60"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className="border-t border-hair/20 hover:bg-elev/30 transition-colors"
            >
              {cols.map((c) => (
                <td
                  key={c}
                  className="px-3 py-2 font-mono text-xs text-ink-dim align-top max-w-[320px] truncate"
                  title={renderCell(row[c])}
                >
                  {renderCell(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}
