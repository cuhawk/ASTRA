"use client";

type Severity = "high" | "medium" | "low";

interface Finding {
  id: string;
  title: string;
  severity: Severity;
  description: string;
  line: number;
  taintTokens: string[];
  sinkLabel?: string;
}

const PLACEHOLDER_FINDINGS: Finding[] = [
  {
    id: "sql-injection-1",
    title: "Potential SQL Injection",
    severity: "high",
    description:
      "User-controlled input flows into a query builder without parameterization. The taint trail crosses the controller boundary unsanitized.",
    line: 18,
    taintTokens: ["user_input", "user_input"],
    sinkLabel: "unsound dst",
  },
  {
    id: "insecure-cred-storage-1",
    title: "Insecure Credential Storage",
    severity: "medium",
    description:
      "Credentials reach a storage helper without hashing. Downstream consumers treat the value as already-hashed, exposing plaintext at rest.",
    line: 52,
    taintTokens: ["user_input", "user_input", "user_input"],
    sinkLabel: "untrusted dst",
  },
];

const SEV_STYLE: Record<
  Severity,
  { rail: string; dot: string; label: string; text: string }
> = {
  high: {
    rail: "border-l-rose-500/80",
    dot: "bg-rose-400",
    label: "High",
    text: "text-rose-300",
  },
  medium: {
    rail: "border-l-amber-500/80",
    dot: "bg-amber-400",
    label: "Medium",
    text: "text-amber-300",
  },
  low: {
    rail: "border-l-cyan-500/80",
    dot: "bg-cyan-400",
    label: "Low",
    text: "text-cyan-300",
  },
};

export function SecurityReport({ collapsible = true }: { collapsible?: boolean }) {
  return (
    <section className="rounded-lg bg-panel/60 card-inset overflow-hidden flex flex-col min-h-0">
      <header className="flex items-center justify-between px-4 py-3 border-b border-hair/40 shrink-0">
        <span className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute">
          Security analysis report
        </span>
        {collapsible ? (
          <button
            type="button"
            className="text-ink-mute hover:text-accent transition"
            title="Collapse"
            aria-label="Collapse"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-3.5 h-3.5"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        ) : null}
      </header>

      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
        {PLACEHOLDER_FINDINGS.map((f) => (
          <FindingCard key={f.id} finding={f} />
        ))}
        <div className="rounded-md border border-dashed border-hair/50 px-3 py-3 text-center font-mono text-[0.62rem] uppercase tracking-[0.22em] text-ink-mute">
          live findings ship next sprint
        </div>
      </div>
    </section>
  );
}

function FindingCard({ finding }: { finding: Finding }) {
  const s = SEV_STYLE[finding.severity];
  return (
    <article
      className={`relative bg-elev/40 rounded-md border border-hair/40 border-l-2 ${s.rail} p-3 flex flex-col gap-2 hover:border-hair/70 transition`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`w-1.5 h-1.5 rounded-full ${s.dot} shrink-0`}
            aria-hidden
          />
          <h3 className="font-mono text-sm text-ink truncate">
            {finding.title}
          </h3>
        </div>
        <button
          className="text-ink-mute hover:text-ink-dim shrink-0"
          aria-label="More"
          title="More"
        >
          <svg
            viewBox="0 0 24 24"
            fill="currentColor"
            className="w-3.5 h-3.5"
            aria-hidden
          >
            <circle cx="5" cy="12" r="1.5" />
            <circle cx="12" cy="12" r="1.5" />
            <circle cx="19" cy="12" r="1.5" />
          </svg>
        </button>
      </div>

      <div className="font-mono text-[0.6rem] uppercase tracking-[0.18em] text-ink-mute">
        Severity: <span className={`${s.text} font-semibold`}>{s.label}</span>
      </div>

      <p className="text-xs text-ink-dim leading-relaxed">{finding.description}</p>

      <div className="border-t border-hair/30 pt-2 flex flex-col gap-1.5">
        <div className="font-mono text-[0.6rem] uppercase tracking-[0.18em] text-ink-mute">
          Line {finding.line}:
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {finding.taintTokens.map((t, i) => (
            <span
              key={i}
              className="font-mono text-[0.62rem] px-1.5 py-0.5 rounded bg-rose-950/40 border border-rose-700/40 text-rose-200"
            >
              TAINTED: {t}
            </span>
          ))}
          {finding.sinkLabel ? (
            <>
              <span className="text-ink-mute font-mono text-xs" aria-hidden>
                →
              </span>
              <span className="font-mono text-[0.62rem] px-1.5 py-0.5 rounded bg-amber-950/40 border border-amber-700/40 text-amber-200">
                {finding.sinkLabel}
              </span>
            </>
          ) : null}
        </div>
      </div>
    </article>
  );
}
