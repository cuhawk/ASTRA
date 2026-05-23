import { redirect } from "next/navigation";
import { apiServer } from "@/lib/api-server";
import { SignOutButton } from "@/components/SignOutButton";
import { FullActivityLog } from "@/components/FullActivityLog";
import { AnthropicKeyCard } from "@/components/AnthropicKeyCard";
import type { ActivityEvent, User, VaultStatus } from "@/lib/types";

async function getUser(): Promise<User | null> {
  try {
    return await apiServer<User>("/auth/me");
  } catch {
    return null;
  }
}

async function getActivity(): Promise<ActivityEvent[]> {
  try {
    return await apiServer<ActivityEvent[]>("/activity?limit=200");
  } catch {
    return [];
  }
}

async function getAnthropicStatus(): Promise<VaultStatus> {
  try {
    return await apiServer<VaultStatus>("/vault/keys/anthropic");
  } catch {
    return { provider: "anthropic", present: false, updated_at: null };
  }
}

export default async function SettingsPage() {
  const user = await getUser();
  if (!user) redirect("/");
  const [activity, anthropicStatus] = await Promise.all([getActivity(), getAnthropicStatus()]);

  return (
    <div className="max-w-[1000px] mx-auto px-5 py-6 flex flex-col gap-6 reveal">
      <header className="flex flex-col gap-1">
        <span className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute">settings</span>
        <h1 className="text-2xl font-semibold tracking-tight font-mono">Settings<span className="text-ink-mute">.</span></h1>
      </header>

      <section className="grid lg:grid-cols-2 gap-3">
        <ProfileCard user={user} />
        <SessionCard />
      </section>

      <section className="flex flex-col gap-2.5">
        <SectionTitle eyebrow="providers" title="api keys" />
        <AnthropicKeyCard initial={anthropicStatus} />
      </section>

      <section className="flex flex-col gap-2.5">
        <SectionTitle eyebrow="audit" title="activity log" />
        <FullActivityLog initial={activity} />
      </section>
    </div>
  );
}

function ProfileCard({ user }: { user: User }) {
  return (
    <div className="rounded-lg bg-panel/50 card-sharp p-5 flex flex-col gap-3">
      <span className="font-mono text-[0.55rem] uppercase tracking-[0.24em] text-ink-mute">profile</span>
      <Field label="github" value={user.github_login} />
      <Field label="github id" value={String(user.github_id)} mono />
      <Field label="email" value={user.email ?? "—"} />
      <Field label="user id" value={String(user.id)} mono />
    </div>
  );
}

function SessionCard() {
  return (
    <div className="rounded-lg bg-panel/50 card-sharp p-5 flex flex-col gap-3">
      <span className="font-mono text-[0.55rem] uppercase tracking-[0.24em] text-ink-mute">session</span>
      <p className="text-ink-dim text-xs leading-relaxed">
        Signed in via GitHub OAuth. Session in signed{" "}
        <code className="font-mono text-accent bg-accent/8 px-1 py-0.5 rounded border border-accent/20 text-[0.72rem]">httponly</code>{" "}
        cookie, 14-day max age.
      </p>
      <div className="mt-auto pt-3 border-t border-hair/20">
        <div className="flex items-center justify-between gap-3">
          <span className="font-mono text-[0.6rem] uppercase tracking-wider text-ink-mute">sign out</span>
          <div className="inline-flex items-center border border-rose-500/30 bg-rose-950/20 hover:bg-rose-900/30 hover:border-rose-500/60 px-3 py-1.5 rounded-md transition">
            <SignOutButton />
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[0.55rem] uppercase tracking-[0.22em] text-ink-mute">{label}</span>
      <span className={(mono ? "font-mono text-xs " : "text-sm ") + "text-ink-dim break-all"}>{value}</span>
    </div>
  );
}

function SectionTitle({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="font-mono text-[0.58rem] uppercase tracking-[0.24em] text-ink-mute">{eyebrow}</span>
      <span className="h-px flex-1 bg-gradient-to-r from-hair via-hair/40 to-transparent" />
      <span className="font-mono text-xs uppercase tracking-[0.18em] text-ink-dim">{title}</span>
    </div>
  );
}
