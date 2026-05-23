"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { humanizeAge } from "@/lib/format";
import type { ActivityEvent } from "@/lib/types";

const POLL_MS = 15_000;
const PAGE_SIZES = [50, 100, 200];

type Filter = "all" | "runs" | "auth" | "chat";

const ACTION_META: Record<string, { label: string; dot: string; bucket: Filter }> = {
  "run.created": { label: "run created", dot: "bg-accent", bucket: "runs" },
  "run.done": { label: "run done", dot: "bg-emerald-400", bucket: "runs" },
  "run.failed": { label: "run failed", dot: "bg-rose-400", bucket: "runs" },
  "run.deleted": { label: "run deleted", dot: "bg-ink-mute", bucket: "runs" },
  "auth.login": { label: "login", dot: "bg-cyan-400", bucket: "auth" },
  "chat.message": { label: "chat message", dot: "bg-fuchsia-400", bucket: "chat" },
};

function metaFor(action: string) {
  return (
    ACTION_META[action] ?? {
      label: action,
      dot: "bg-hair-bright",
      bucket: "all" as Filter,
    }
  );
}

function formatTime(at: number): string {
  return new Date(at * 1000).toLocaleString();
}

interface Props {
  initial: ActivityEvent[];
}

export function FullActivityLog({ initial }: Props) {
  const [events, setEvents] = useState<ActivityEvent[]>(initial);
  const [filter, setFilter] = useState<Filter>("all");
  const [pageSize, setPageSize] = useState<number>(50);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      setRefreshing(true);
      try {
        const next = await api<ActivityEvent[]>(`/activity?limit=${pageSize}`);
        if (!cancelled) setEvents(next);
      } catch {
        /* keep stale data */
      } finally {
        if (!cancelled) setRefreshing(false);
      }
      if (!cancelled) timer = setTimeout(tick, POLL_MS);
    }
    timer = setTimeout(tick, POLL_MS);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [pageSize]);

  async function reloadNow() {
    setRefreshing(true);
    try {
      const next = await api<ActivityEvent[]>(`/activity?limit=${pageSize}`);
      setEvents(next);
    } catch {
      /* ignore */
    } finally {
      setRefreshing(false);
    }
  }

  const filtered = useMemo(() => {
    if (filter === "all") return events;
    return events.filter((e) => metaFor(e.action).bucket === filter);
  }, [events, filter]);

  const counts = useMemo(() => {
    const c = { all: events.length, runs: 0, auth: 0, chat: 0 };
    for (const e of events) {
      const b = metaFor(e.action).bucket;
      if (b !== "all") c[b]++;
    }
    return c;
  }, [events]);

  return (
    <div className="rounded-lg bg-panel/60 card-inset overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 px-5 py-3 border-b border-hair/40">
        <div className="flex items-center gap-1">
          <FilterPill
            active={filter === "all"}
            onClick={() => setFilter("all")}
            label="all"
            count={counts.all}
          />
          <FilterPill
            active={filter === "runs"}
            onClick={() => setFilter("runs")}
            label="runs"
            count={counts.runs}
          />
          <FilterPill
            active={filter === "auth"}
            onClick={() => setFilter("auth")}
            label="auth"
            count={counts.auth}
          />
          <FilterPill
            active={filter === "chat"}
            onClick={() => setFilter("chat")}
            label="chat"
            count={counts.chat}
          />
        </div>
        <div className="ml-auto flex items-center gap-3">
          <label className="font-mono text-[0.62rem] uppercase tracking-wider text-ink-mute flex items-center gap-2">
            limit
            <select
              value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}
              className="bg-void/60 border border-hair/60 rounded-md px-2 py-1 text-ink font-mono text-xs focus:outline-none focus:border-accent/60"
            >
              {PAGE_SIZES.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={reloadNow}
            disabled={refreshing}
            className="font-mono text-[0.62rem] uppercase tracking-wider text-ink-mute hover:text-accent disabled:opacity-50 transition"
          >
            {refreshing ? "…" : "refresh"}
          </button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="px-5 py-12 text-center text-ink-mute font-mono text-sm">
          no events match this filter
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead className="bg-elev/30 border-b border-hair/40">
            <tr className="text-left">
              <th className="px-5 py-3 font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute">
                action
              </th>
              <th className="px-5 py-3 font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute">
                entity
              </th>
              <th className="px-5 py-3 font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute">
                id
              </th>
              <th className="px-5 py-3 font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute">
                detail
              </th>
              <th className="px-5 py-3 text-right font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute">
                when
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e) => {
              const meta = metaFor(e.action);
              const detail = renderDetail(e);
              const href = e.entity === "run" && e.entity_id
                ? `/runs/${e.entity_id}`
                : null;
              return (
                <tr
                  key={e.id}
                  className="border-t border-hair/20 hover:bg-elev/30 transition-colors"
                >
                  <td className="px-5 py-3">
                    <span className="inline-flex items-center gap-2 font-mono text-xs">
                      <span
                        className={`inline-block w-1.5 h-1.5 rounded-full ${meta.dot}`}
                        aria-hidden
                      />
                      {meta.label}
                    </span>
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-ink-mute">
                    {e.entity}
                  </td>
                  <td className="px-5 py-3 font-mono text-xs">
                    {e.entity_id ? (
                      href ? (
                        <Link
                          href={href}
                          className="text-accent hover:underline underline-offset-2"
                        >
                          {e.entity_id.slice(0, 12)}
                        </Link>
                      ) : (
                        <span className="text-ink-dim">
                          {e.entity_id.slice(0, 12)}
                        </span>
                      )
                    ) : (
                      <span className="text-ink-mute">—</span>
                    )}
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-ink-dim max-w-md truncate">
                    {detail || <span className="text-ink-mute">—</span>}
                  </td>
                  <td
                    className="px-5 py-3 text-right font-mono text-xs text-ink-mute tabular-nums whitespace-nowrap"
                    title={formatTime(e.at)}
                  >
                    {humanizeAge(e.at)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function FilterPill({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "inline-flex items-center gap-2 px-3 py-1 rounded-md font-mono text-[0.65rem] uppercase tracking-wider transition " +
        (active
          ? "bg-accent/15 text-accent border border-accent/40"
          : "text-ink-mute hover:text-ink-dim border border-transparent")
      }
    >
      {label}
      <span className="tabular-nums text-ink-mute">{count}</span>
    </button>
  );
}

function renderDetail(e: ActivityEvent): string {
  const p = e.payload;
  if (!p) return "";
  if (e.action === "run.created") return String(p.url ?? "");
  if (e.action === "run.done")
    return `${p.functions ?? 0} fn · ${p.edges ?? 0} edge · ${p.files ?? 0} files`;
  if (e.action === "run.failed") {
    const stage = p.stage ? `[${p.stage}] ` : "";
    return `${stage}${(p.error as string) ?? ""}`;
  }
  if (e.action === "auth.login") return String(p.login ?? "");
  if (e.action === "chat.message") return `len=${p.len ?? 0}`;
  try {
    return JSON.stringify(p);
  } catch {
    return "";
  }
}
