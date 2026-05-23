"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";
import { humanizeAge } from "@/lib/format";
import type { Feature } from "@/lib/types";

export default function FeaturesPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;
  const [features, setFeatures] = useState<Feature[]>([]);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recordingFor, setRecordingFor] = useState<string | null>(null);

  async function refresh() {
    if (!runId) return;
    try {
      const list = await api<Feature[]>(`/runs/${runId}/features`);
      setFeatures(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  async function createFeature(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setCreating(true);
    try {
      await api<Feature>(`/runs/${runId}/features`, {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setName("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="max-w-[1200px] mx-auto px-6 py-10 flex flex-col gap-8 reveal">
      <header className="flex flex-col gap-3">
        <Link
          href={`/runs/${runId}`}
          className="font-mono text-[0.65rem] uppercase tracking-[0.22em] text-ink-mute hover:text-accent w-fit"
        >
          ← back to run
        </Link>
        <div className="flex items-end justify-between flex-wrap gap-3">
          <div className="flex flex-col gap-1">
            <span className="font-mono text-[0.65rem] uppercase tracking-[0.24em] text-ink-mute">
              runtime coverage · feature labels
            </span>
            <h1 className="text-3xl font-semibold tracking-tight">
              Features<span className="text-ink-mute">.</span>
            </h1>
          </div>
        </div>
      </header>

      <div className="rounded-lg bg-panel/60 card-inset p-5">
        <form
          onSubmit={createFeature}
          className="flex flex-col sm:flex-row gap-3"
        >
          <div className="flex-1">
            <label className="flex flex-col gap-1.5">
              <span className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute">
                feature name
              </span>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="login · checkout · search · admin-panel"
                className="bg-void/60 border border-hair rounded-md px-3 py-2.5 font-mono text-sm text-ink placeholder:text-ink-mute focus-phosphor"
              />
            </label>
          </div>
          <div className="self-end">
            <Button
              type="submit"
              size="lg"
              disabled={creating || name.length === 0}
            >
              {creating ? "creating" : "+ create"}
            </Button>
          </div>
        </form>
      </div>

      {error ? (
        <div className="rounded-md border border-rose-700/60 bg-rose-950/30 text-rose-300 font-mono text-xs p-3 whitespace-pre-wrap break-words">
          {error}
        </div>
      ) : null}

      {features.length === 0 ? (
        <div className="rounded-lg bg-panel/40 card-inset p-12 text-center flex flex-col items-center gap-4">
          <pre className="font-mono text-[0.7rem] text-ink-mute leading-tight">
            {`  ◯───◯\n  │   │\n  ◯───◯`}
          </pre>
          <p className="text-ink">No features yet.</p>
          <p className="text-ink-mute text-sm font-mono">
            Create one, then point Chrome at it to record what executes.
          </p>
        </div>
      ) : (
        <div className="grid gap-3">
          {features.map((f) => (
            <FeatureCard
              key={f.id}
              feature={f}
              runId={runId}
              recording={recordingFor === f.id}
              onToggleRecord={() =>
                setRecordingFor(recordingFor === f.id ? null : f.id)
              }
              onRecorded={async () => {
                setRecordingFor(null);
                await refresh();
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FeatureCard({
  feature,
  runId,
  recording,
  onToggleRecord,
  onRecorded,
}: {
  feature: Feature;
  runId: string;
  recording: boolean;
  onToggleRecord: () => void;
  onRecorded: () => void;
}) {
  return (
    <div className="rounded-lg bg-panel/60 card-inset card-inset-hover transition-shadow">
      <div className="px-5 py-4 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <span
            className="inline-block w-2 h-2 rounded-full bg-accent"
            aria-hidden
          />
          <span className="font-mono text-base text-ink truncate">
            {feature.name}
          </span>
          <StatusBadge status={feature.last_status} />
        </div>
        <div className="flex items-center gap-4 font-mono text-xs">
          <span className="text-ink-mute">
            matched{" "}
            <span className="text-ink-dim tabular-nums">
              {feature.matched_functions}
            </span>
          </span>
          {feature.last_run_at ? (
            <span className="text-ink-mute">
              {humanizeAge(feature.last_run_at)}
            </span>
          ) : null}
          <Button variant="ghost" size="sm" onClick={onToggleRecord}>
            {recording ? "cancel" : "record"}
          </Button>
        </div>
      </div>
      {feature.error ? (
        <pre className="mx-5 mb-4 rounded-md border border-rose-700/40 bg-rose-950/20 text-rose-300 text-xs font-mono whitespace-pre-wrap break-words p-3">
          {feature.error}
        </pre>
      ) : null}
      {recording ? (
        <RecordForm
          runId={runId}
          featureId={feature.id}
          onDone={onRecorded}
        />
      ) : null}
    </div>
  );
}

function RecordForm({
  runId,
  featureId,
  onDone,
}: {
  runId: string;
  featureId: string;
  onDone: () => void;
}) {
  const [url, setUrl] = useState("");
  const [selector, setSelector] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api(`/runs/${runId}/features/${featureId}/record`, {
        method: "POST",
        body: JSON.stringify({
          url,
          actions: [
            { type: "click", selector },
            { type: "wait", ms: 200 },
          ],
        }),
      });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="border-t border-hair/40 px-5 py-4 bg-elev/30 flex flex-col gap-3"
    >
      <div className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-cyan-400">
        record session
      </div>
      <div className="grid sm:grid-cols-[1fr_1fr] gap-3">
        <label className="flex flex-col gap-1.5">
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute">
            url
          </span>
          <input
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/login"
            className="bg-void/60 border border-hair rounded-md px-3 py-2 font-mono text-sm text-ink placeholder:text-ink-mute focus-phosphor"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute">
            click selector
          </span>
          <input
            type="text"
            required
            value={selector}
            onChange={(e) => setSelector(e.target.value)}
            placeholder="button[type=submit]"
            className="bg-void/60 border border-hair rounded-md px-3 py-2 font-mono text-sm text-ink placeholder:text-ink-mute focus-phosphor"
          />
        </label>
      </div>
      {error ? (
        <div className="rounded-md border border-rose-700/60 bg-rose-950/30 text-rose-300 font-mono text-xs p-3 whitespace-pre-wrap break-words">
          {error}
        </div>
      ) : null}
      <div>
        <Button type="submit" disabled={submitting} size="sm">
          {submitting ? "recording" : "start recording"}
        </Button>
      </div>
    </form>
  );
}
