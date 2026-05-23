"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { humanizeAge } from "@/lib/format";
import type { ChatMessage } from "@/lib/types";

interface Props {
  runId: string;
}

export function RunChat({ runId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<ChatMessage[]>(`/runs/${runId}/chat`)
      .then((rows) => {
        if (!cancelled) setMessages(rows);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [runId]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending]);

  async function send() {
    const trimmed = input.trim();
    if (!trimmed || sending) return;
    setError(null);
    setSending(true);

    const optimistic: ChatMessage = {
      id: -Date.now(),
      run_id: runId,
      role: "user",
      content: trimmed,
      llm_call_id: null,
      created_at: Math.floor(Date.now() / 1000),
    };
    setMessages((prev) => [...prev, optimistic]);
    setInput("");

    try {
      const reply = await api<ChatMessage>(`/runs/${runId}/chat`, {
        method: "POST",
        body: JSON.stringify({ message: trimmed }),
      });
      // Refresh from server so the optimistic user message gets its real id.
      const next = await api<ChatMessage[]>(`/runs/${runId}/chat`);
      setMessages(next);
      // (reply is included in `next`; we just trigger a single source of truth.)
      void reply;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      // Roll back the optimistic message.
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setInput(trimmed);
    } finally {
      setSending(false);
    }
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="grid lg:grid-cols-[1fr_320px] gap-4">
      <div className="rounded-lg bg-panel/60 card-inset flex flex-col h-[60vh] min-h-[480px] overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-hair/40 shrink-0">
          <span className="font-mono text-[0.62rem] uppercase tracking-[0.22em] text-ink-mute">
            chat · gemini flash lite
          </span>
          <span className="font-mono text-[0.62rem] tabular-nums text-ink-mute">
            {messages.length} msg
          </span>
        </div>

        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4"
        >
          {!loaded ? (
            <div className="text-ink-mute font-mono text-sm flex items-center gap-3">
              <span className="inline-block w-3 h-3 border-2 border-accent border-t-transparent rounded-full orbit" />
              loading thread…
            </div>
          ) : messages.length === 0 ? (
            <EmptyChat />
          ) : (
            messages.map((m) => <Bubble key={m.id} message={m} />)
          )}
          {sending ? (
            <div className="flex items-center gap-3 text-ink-mute font-mono text-xs">
              <span className="inline-block w-2.5 h-2.5 border-2 border-accent border-t-transparent rounded-full orbit" />
              assistant thinking…
            </div>
          ) : null}
        </div>

        {error ? (
          <div className="px-5 py-2 border-t border-rose-700/40 bg-rose-950/30 font-mono text-xs text-rose-200">
            {error}
          </div>
        ) : null}

        <div className="border-t border-hair/40 px-3 py-3 flex items-end gap-2 shrink-0">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="Ask about this run — functions, structure, behavior…"
            rows={2}
            className="flex-1 resize-none bg-void/60 border border-hair/60 rounded-md px-3 py-2 font-mono text-sm text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/40"
          />
          <button
            type="button"
            onClick={send}
            disabled={sending || !input.trim()}
            className="bg-accent text-void px-4 py-2 rounded-md font-mono text-xs uppercase tracking-wider hover:bg-accent/90 active:translate-y-px transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? "…" : "send"}
          </button>
        </div>
      </div>

      <aside className="rounded-lg bg-panel/60 card-inset p-5 flex flex-col gap-3 min-h-[300px]">
        <span className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute">
          context
        </span>
        <p className="text-ink-dim text-xs leading-relaxed">
          Gemini Flash Lite is grounded in this run only — it sees the function
          count, edges, and a small sample of top functions. Cross-run answers
          are out of scope.
        </p>
        <ul className="flex flex-col gap-2 text-[0.7rem] font-mono text-ink-mute">
          <li>· terse answers, technical tone</li>
          <li>· no hallucinated functions / files</li>
          <li>
            · ⌘/Ctrl + Enter to send
          </li>
        </ul>
      </aside>
    </div>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div
      className={`flex flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}
    >
      <div className="flex items-center gap-2">
        <span
          className={
            "inline-block w-1.5 h-1.5 rounded-full " +
            (isUser ? "bg-accent" : "bg-cyan-400")
          }
        />
        <span className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute">
          {isUser ? "you" : "astra"}
        </span>
        <span className="font-mono text-[0.55rem] text-ink-mute tabular-nums">
          {humanizeAge(message.created_at)}
        </span>
      </div>
      <div
        className={
          "max-w-[85%] px-4 py-2.5 rounded-lg font-mono text-sm whitespace-pre-wrap break-words " +
          (isUser
            ? "bg-accent/10 border border-accent/30 text-ink"
            : "bg-elev/40 border border-hair/50 text-ink-dim")
        }
      >
        {message.content}
      </div>
    </div>
  );
}

function EmptyChat() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 text-ink-mute">
      <pre className="font-mono text-[0.7rem] leading-tight select-none">
        {`  ·   ·\n· [ ?\n  ·`}
      </pre>
      <p className="text-xs font-mono uppercase tracking-wider">
        ask anything about this run
      </p>
    </div>
  );
}
