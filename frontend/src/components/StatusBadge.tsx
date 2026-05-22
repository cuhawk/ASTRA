type Status = string | null | undefined;

const palette: Record<string, string> = {
  pending: "bg-amber-900/40 text-amber-300 border-amber-700/50",
  acquiring: "bg-amber-900/40 text-amber-300 border-amber-700/50",
  analyzing: "bg-amber-900/40 text-amber-300 border-amber-700/50",
  recording: "bg-amber-900/40 text-amber-300 border-amber-700/50",
  done: "bg-emerald-900/40 text-emerald-300 border-emerald-700/50",
  failed: "bg-red-900/40 text-red-300 border-red-700/50",
};

export function StatusBadge({ status }: { status: Status }) {
  const key = status ?? "pending";
  const cls = palette[key] ?? "bg-zinc-800 text-zinc-300 border-zinc-700";
  return (
    <span
      className={`inline-block px-2 py-0.5 text-xs font-medium border rounded ${cls}`}
    >
      {key}
    </span>
  );
}
