import Link from "next/link";
import { redirect } from "next/navigation";
import { apiServer } from "@/lib/api-server";
import { StatusBadge } from "@/components/StatusBadge";
import { DeleteRunButton } from "@/components/DeleteRunButton";
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
    <div className="max-w-[1200px] mx-auto px-6 py-10 flex flex-col gap-8 reveal">
      <header className="flex flex-col gap-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1.5">
            <span className="font-mono text-[0.65rem] uppercase tracking-[0.24em] text-ink-mute">
              workspace · {user.github_login}
            </span>
            <h1 className="text-3xl font-semibold tracking-tight">
              Runs<span className="text-ink-mute">.</span>
            </h1>
          </div>
          <Link
            href="/runs/new"
            className="inline-flex items-center gap-2 bg-accent text-void px-5 py-2.5 rounded-md font-mono text-xs uppercase tracking-wider hover:bg-accent/90 hover:shadow-[0_0_22px_-4px_rgba(16,185,129,0.65)] active:translate-y-px transition-all"
          >
            <span className="text-base leading-none">+</span> new run
          </Link>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCell label="total" value={counts.total} />
          <StatCell label="done" value={counts.done} tone="accent" />
          <StatCell label="in-flight" value={counts.inFlight} tone="amber" />
          <StatCell label="failed" value={counts.failed} tone="rose" />
        </div>
      </header>

      {runs.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="relative rounded-lg bg-panel/60 card-inset overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-elev/40 border-b border-hair/60">
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
                  className="group row-edge border-t border-hair/30 hover:bg-elev/30 transition-colors"
                >
                  <td className="px-5 py-3.5 font-mono text-accent">
                    <Link
                      href={`/runs/${r.id}`}
                      className="hover:underline underline-offset-2"
                    >
                      {r.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td
                    className="px-5 py-3.5 text-ink-dim max-w-xs truncate"
                    title={r.url ?? ""}
                  >
                    <span className="font-mono text-[0.82rem]">
                      {truncate(r.url, 50)}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-5 py-3.5 text-ink-mute font-mono text-xs">
                    {humanizeAge(r.created_at)}
                  </td>
                  <td className="px-5 py-3.5 text-right font-mono text-ink-dim tabular-nums">
                    {r.files}
                  </td>
                  <td className="px-5 py-3.5 text-right font-mono text-ink-dim tabular-nums">
                    {r.functions}
                  </td>
                  <td className="px-5 py-3.5 text-right font-mono text-ink-dim tabular-nums">
                    {r.edges}
                  </td>
                  <td className="px-3 py-3.5 text-right w-20">
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

function Th({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      className={`px-5 py-3 font-mono text-[0.62rem] uppercase tracking-[0.22em] text-ink-mute ${
        align === "right" ? "text-right" : ""
      }`}
    >
      {children}
    </th>
  );
}

type Tone = "default" | "accent" | "amber" | "rose";

function StatCell({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: number;
  tone?: Tone;
}) {
  const toneText: Record<Tone, string> = {
    default: "text-ink",
    accent: "text-accent",
    amber: "text-amber-300",
    rose: "text-rose-300",
  };
  return (
    <div className="rounded-lg bg-panel/50 card-inset p-4 flex flex-col gap-1">
      <span className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute">
        {label}
      </span>
      <span
        className={`font-mono text-2xl tabular-nums tracking-tight ${toneText[tone]}`}
      >
        {value}
      </span>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg bg-panel/40 card-inset p-12 text-center flex flex-col items-center gap-4">
      <pre className="font-mono text-[0.72rem] text-ink-mute leading-tight select-none">
        {`    ·   ·   ·\n  ·   [ ]   ·\n    ·   ·   ·`}
      </pre>
      <div className="flex flex-col gap-1.5">
        <p className="text-ink">
          The graph is empty.
        </p>
        <p className="text-ink-mute text-sm font-mono">
          No runs yet —{" "}
          <Link
            href="/runs/new"
            className="text-accent hover:underline underline-offset-2"
          >
            point ASTRA at a URL
          </Link>{" "}
          to begin.
        </p>
      </div>
    </div>
  );
}
