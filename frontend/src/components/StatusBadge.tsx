type Status = string | null | undefined;

interface Tone {
  ring: string;
  text: string;
  dot: string;
  pulse: boolean;
  bg: string;
}

const palette: Record<string, Tone> = {
  pending: {
    ring: "border-amber-700/50",
    text: "text-amber-300",
    dot: "bg-amber-400",
    pulse: true,
    bg: "bg-amber-950/30",
  },
  acquiring: {
    ring: "border-amber-700/50",
    text: "text-amber-300",
    dot: "bg-amber-400",
    pulse: true,
    bg: "bg-amber-950/30",
  },
  analyzing: {
    ring: "border-cyan-700/50",
    text: "text-cyan-300",
    dot: "bg-cyan-400",
    pulse: true,
    bg: "bg-cyan-950/30",
  },
  recording: {
    ring: "border-cyan-700/50",
    text: "text-cyan-300",
    dot: "bg-cyan-400",
    pulse: true,
    bg: "bg-cyan-950/30",
  },
  done: {
    ring: "border-emerald-700/60",
    text: "text-emerald-300",
    dot: "bg-emerald-400",
    pulse: false,
    bg: "bg-emerald-950/30",
  },
  failed: {
    ring: "border-rose-700/60",
    text: "text-rose-300",
    dot: "bg-rose-500",
    pulse: false,
    bg: "bg-rose-950/30",
  },
};

const fallback: Tone = {
  ring: "border-hair",
  text: "text-ink-dim",
  dot: "bg-ink-mute",
  pulse: false,
  bg: "bg-elev/40",
};

export function StatusBadge({ status }: { status: Status }) {
  const key = status ?? "pending";
  const tone = palette[key] ?? fallback;
  return (
    <span
      className={`inline-flex items-center gap-2 px-2.5 py-1 text-[0.65rem] font-mono uppercase tracking-[0.18em] border rounded-md ${tone.ring} ${tone.text} ${tone.bg}`}
    >
      <span
        className={`inline-block w-1.5 h-1.5 rounded-full ${tone.dot} ${
          tone.pulse ? "pulse-dot" : ""
        }`}
        aria-hidden
      />
      {key}
    </span>
  );
}
