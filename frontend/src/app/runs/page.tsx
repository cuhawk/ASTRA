import Link from "next/link";
import { redirect } from "next/navigation";
import { apiServer } from "@/lib/api-server";
import { StatusBadge } from "@/components/StatusBadge";
import { DeleteRunButton } from "@/components/DeleteRunButton";
import { NewRunButton } from "@/components/NewRunButton";
import { humanizeAge, truncate } from "@/lib/format";
import type { Run, User } from "@/lib/types";

async function getUser(): Promise<User | null> {
  try {
    return await apiServer<User>("/auth/me");
  } catch {
    return null;
  }
}

async function getRuns(): Promise<Run[]> {
  try {
    return await apiServer<Run[]>("/runs");
  } catch {
    return [];
  }
}

export default async function RunsPage() {
  const user = await getUser();
  if (!user) redirect("/");
  const runs = await getRuns();

  const counts = {
    total: runs.length,
    done: runs.filter((r) => r.status === "done").length,
    inFlight: runs.filter((r) =>
      ["pending", "acquiring", "analyzing"].includes(r.status),
    ).length,
    failed: runs.filter((r) => r.status === "failed").length,
  };

  return (
    <div className="max-w-[1200px] mx-auto px-4 md:px-5 py-6 flex flex-col gap-5 reveal">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute">
            runs
          </span>
          <h1 className="text-2xl font-semibold tracking-tight font-mono">
            Runs<span className="text-ink-mute">.</span>
          </h1>
        </div>
        <NewRunButton />
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <StatCell label="total" value={counts.total} />
        <StatCell label="done" value={counts.done} tone="accent" />
        <StatCell label="in-flight" value={counts.inFlight} tone="amber" />
        <StatCell label="failed" value={counts.failed} tone="rose" />
      </div>

      {runs.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="rounded-lg bg-panel/50 card-sharp overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead className="bg-elev/30 border-b border-hair/50">
              <tr className="text-left">
                <Th>id</Th>
                <Th>url</Th>
                <Th>status</Th>
                <Th>created</Th>
                <Th align="right">files</Th>
                <Th align="right">funcs</Th>
                <Th align="right">edges</Th>
                <Th align="right"> </Th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr
                  key={r.id}
                  className="group row-edge border-t border-hair/20 hover:bg-elev/20 transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-accent text-[0.82rem]">
                    <Link
                      href={`/runs/${r.id}`}
                      className="hover:underline underline-offset-2"
                    >
                      {r.id.slice(0, 10)}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-ink-dim max-w-xs truncate" title={r.url ?? ""}>
                    <span className="font-mono text-[0.78rem]">{truncate(r.url, 48)}</span>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-4 py-3 text-ink-mute font-mono text-[0.72rem]">
                    {humanizeAge(r.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink-dim tabular-nums text-[0.82rem]">
                    {r.files}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink-dim tabular-nums text-[0.82rem]">
                    {r.functions}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink-dim tabular-nums text-[0.82rem]">
                    {r.edges}
                  </td>
                  <td className="px-3 py-3 text-right w-16">
                    <DeleteRunButton runId={r.id} variant="row" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Th({ children, align = "left" }: { children: React.ReactNode; align?: "left" | "right" }) {
  return (
    <th className={`px-4 py-2.5 font-mono text-[0.58rem] uppercase tracking-[0.22em] text-ink-mute font-normal ${align === "right" ? "text-right" : ""}`}>
      {children}
    </th>
  );
}

type Tone = "default" | "accent" | "amber" | "rose";

function StatCell({ label, value, tone = "default" }: { label: string; value: number; tone?: Tone }) {
  const toneText: Record<Tone, string> = {
    default: "text-ink",
    accent: "text-accent",
    amber: "text-amber-300",
    rose: "text-rose-300",
  };
  return (
    <div className="rounded-lg bg-panel/40 card-sharp p-3.5 flex flex-col gap-1">
      <span className="font-mono text-[0.55rem] uppercase tracking-[0.24em] text-ink-mute">{label}</span>
      <span className={`font-mono text-xl tabular-nums tracking-tight ${toneText[tone]}`}>{value}</span>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg bg-panel/30 card-sharp p-10 text-center flex flex-col items-center gap-3">
      <pre className="font-mono text-[0.7rem] text-ink-mute leading-tight select-none">
        {`    ·   ·   ·\n  ·   [ ]   ·\n    ·   ·   ·`}
      </pre>
      <p className="text-ink text-sm">The graph is empty.</p>
      <p className="text-ink-mute text-xs font-mono">
        Create a new run to begin.
      </p>
      <NewRunButton />
    </div>
  );
}
