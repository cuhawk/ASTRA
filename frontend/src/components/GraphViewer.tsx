"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type {
  Core,
  ElementDefinition,
  NodeSingular,
  StylesheetCSS,
} from "cytoscape";
import CytoscapeComponent from "react-cytoscapejs";
import { api } from "@/lib/api";

interface FunctionRow {
  id: string;
  name?: string | null;
  path?: string | null;
  start_line?: number | null;
  end_line?: number | null;
}

interface EdgeRow {
  source: string;
  target: string;
}

interface SelectedNode {
  id: string;
  name?: string | null;
  path?: string | null;
  start_line?: number | null;
  end_line?: number | null;
}

type CypherOut<T extends object = Record<string, unknown>> = {
  cypher: string;
  rows: T[];
  row_count: number;
  duration_ms: number;
};

// Cheap deterministic hue derivation from string.
function hashHue(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h) % 360;
}

function colorForPath(path?: string | null): string {
  if (!path) return "#10b981";
  // First two path segments dominate the hue.
  const seg = path.split("/").slice(0, 2).join("/");
  const hue = hashHue(seg);
  // Constrain to teal-blue-cyan-green band to keep the dark aesthetic.
  return `oklch(0.7 0.15 ${(hue % 90) + 150})`;
}

export function GraphViewer({ runId }: { runId: string }) {
  const cyRef = useRef<Core | null>(null);
  const [funcs, setFuncs] = useState<FunctionRow[] | null>(null);
  const [edges, setEdges] = useState<EdgeRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hideIsolated, setHideIsolated] = useState(true);
  const [selected, setSelected] = useState<SelectedNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [totalFuncs, setTotalFuncs] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [fRes, eRes] = await Promise.all([
          api<CypherOut<FunctionRow>>(`/runs/${runId}/cypher`, {
            method: "POST",
            body: JSON.stringify({
              query:
                "MATCH (f:Function) RETURN f.id AS id, f.name AS name, f.path AS path, f.start_line AS start_line, f.end_line AS end_line LIMIT 500",
            }),
          }),
          api<CypherOut<EdgeRow>>(`/runs/${runId}/cypher`, {
            method: "POST",
            body: JSON.stringify({
              query:
                "MATCH (a:Function)-[:CALLS]->(b:Function) RETURN a.id AS source, b.id AS target LIMIT 1000",
            }),
          }),
        ]);
        if (cancelled) return;
        setFuncs(fRes.rows);
        setEdges(eRes.rows);
        // Best-effort total count — non-blocking
        try {
          const cRes = await api<CypherOut<{ n: number }>>(
            `/runs/${runId}/cypher`,
            {
              method: "POST",
              body: JSON.stringify({
                query: "MATCH (f:Function) RETURN count(f) AS n",
              }),
            },
          );
          if (!cancelled && cRes.rows[0]) setTotalFuncs(cRes.rows[0].n);
        } catch {
          /* ignore */
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  const elements = useMemo<ElementDefinition[]>(() => {
    if (!funcs || !edges) return [];
    const ids = new Set(funcs.map((f) => f.id));
    const filteredEdges = edges.filter(
      (e) => ids.has(e.source) && ids.has(e.target),
    );
    const connected = new Set<string>();
    if (hideIsolated) {
      filteredEdges.forEach((e) => {
        connected.add(e.source);
        connected.add(e.target);
      });
    }
    const visibleFuncs = hideIsolated
      ? funcs.filter((f) => connected.has(f.id))
      : funcs;

    const nodes: ElementDefinition[] = visibleFuncs.map((f) => ({
      data: {
        id: f.id,
        label: f.name ?? f.id.slice(0, 6),
        path: f.path ?? "",
        startLine: f.start_line ?? null,
        endLine: f.end_line ?? null,
        color: colorForPath(f.path),
      },
    }));
    const edgeEls: ElementDefinition[] = filteredEdges
      .filter(
        (e) =>
          !hideIsolated ||
          (connected.has(e.source) && connected.has(e.target)),
      )
      .map((e, i) => ({
        data: { id: `e${i}`, source: e.source, target: e.target },
      }));
    return [...nodes, ...edgeEls];
  }, [funcs, edges, hideIsolated]);

  const stylesheet = useMemo<StylesheetCSS[]>(
    () => ([
      {
        selector: "node",
        style: {
          "background-color": "data(color)",
          width: 14,
          height: 14,
          label: "data(label)",
          color: "#a1a8b3",
          "font-family":
            "var(--font-jetbrains), ui-monospace, SFMono-Regular, monospace",
          "font-size": "8px",
          "text-margin-y": -6,
          "text-outline-color": "#15171c",
          "text-outline-width": 2,
          "border-width": 1,
          "border-color": "rgba(255,255,255,0.18)",
          "transition-property": "background-color, border-color, width, height",
          "transition-duration": 120,
        },
      },
      {
        selector: "node:selected",
        style: {
          "border-color": "#10b981",
          "border-width": 2.5,
          width: 18,
          height: 18,
          "z-index": 99,
        },
      },
      {
        selector: "edge",
        style: {
          width: 0.8,
          "line-color": "rgba(120,160,200,0.18)",
          "curve-style": "bezier",
          "target-arrow-shape": "triangle",
          "target-arrow-color": "rgba(120,160,200,0.28)",
          "arrow-scale": 0.6,
        },
      },
      {
        selector: "edge:selected",
        style: {
          "line-color": "rgba(16,185,129,0.7)",
          "target-arrow-color": "rgba(16,185,129,0.9)",
          width: 1.6,
        },
      },
    ]) as unknown as StylesheetCSS[],
    [],
  );

  const onCyInit = (cy: Core) => {
    cyRef.current = cy;
    cy.on("tap", "node", (evt) => {
      const n = evt.target as NodeSingular;
      const d = n.data();
      setSelected({
        id: d.id,
        name: d.label,
        path: d.path,
        start_line: d.startLine,
        end_line: d.endLine,
      });
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) setSelected(null);
    });
  };

  const layout = useMemo(
    () => ({
      name: "cose",
      animate: false,
      nodeRepulsion: 8000,
      idealEdgeLength: 60,
      gravity: 0.25,
      numIter: 1200,
      randomize: true,
      fit: true,
      padding: 30,
    }),
    [],
  );

  if (error) {
    return (
      <div className="rounded-lg border border-rose-700/60 bg-rose-950/30 p-6 text-rose-300 font-mono text-sm whitespace-pre-wrap">
        graph load failed: {error}
      </div>
    );
  }

  if (loading || !funcs || !edges) {
    return (
      <div className="rounded-lg bg-panel/60 card-inset h-[60vh] flex items-center justify-center text-ink-mute font-mono text-sm">
        <span className="inline-flex items-center gap-3">
          <span className="inline-block w-3 h-3 border-2 border-accent border-t-transparent rounded-full orbit" />
          materializing callgraph…
        </span>
      </div>
    );
  }

  const visibleNodeCount = elements.filter((e) => !("source" in (e.data ?? {})))
    .length;
  const visibleEdgeCount = elements.length - visibleNodeCount;

  return (
    <div className="grid lg:grid-cols-[1fr_320px] gap-4">
      <div className="relative rounded-lg bg-panel/60 card-inset overflow-hidden">
        <div className="absolute top-3 left-3 z-10 flex flex-wrap items-center gap-2 pointer-events-none">
          <span className="pointer-events-auto inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-void/80 border border-hair/70 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-ink-mute">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent" />
            nodes <span className="text-ink-dim tabular-nums">{visibleNodeCount}</span>
            <span className="text-hair-bright">·</span>
            edges{" "}
            <span className="text-ink-dim tabular-nums">{visibleEdgeCount}</span>
          </span>
          {totalFuncs !== null && totalFuncs > funcs.length ? (
            <span className="pointer-events-auto inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-amber-950/40 border border-amber-700/40 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-amber-300">
              showing first 500 of{" "}
              <span className="tabular-nums">{totalFuncs}</span>
            </span>
          ) : null}
        </div>
        <div className="absolute top-3 right-3 z-10">
          <label className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-void/80 border border-hair/70 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-ink-dim cursor-pointer hover:text-accent transition">
            <input
              type="checkbox"
              checked={hideIsolated}
              onChange={(e) => setHideIsolated(e.target.checked)}
              className="accent-emerald-500"
            />
            hide isolated
          </label>
        </div>
        <CytoscapeComponent
          elements={elements}
          stylesheet={stylesheet}
          layout={layout}
          cy={onCyInit}
          className="cy-host"
          style={{ width: "100%", height: "60vh", minHeight: "480px" }}
        />
      </div>

      <aside className="rounded-lg bg-panel/60 card-inset p-5 flex flex-col gap-4 min-h-[300px]">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute">
            inspector
          </span>
          {selected ? (
            <button
              onClick={() => {
                setSelected(null);
                cyRef.current?.$(":selected").unselect();
              }}
              className="font-mono text-[0.65rem] uppercase tracking-wider text-ink-mute hover:text-accent"
            >
              clear
            </button>
          ) : null}
        </div>
        {selected ? (
          <div className="flex flex-col gap-3 text-sm">
            <div>
              <div className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute mb-1">
                name
              </div>
              <div className="font-mono text-accent text-base break-all">
                {selected.name ?? "—"}
              </div>
            </div>
            <div>
              <div className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute mb-1">
                id
              </div>
              <div className="font-mono text-xs text-ink-dim break-all">
                {selected.id}
              </div>
            </div>
            <div>
              <div className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute mb-1">
                path
              </div>
              <div className="font-mono text-xs text-ink-dim break-all">
                {selected.path || "—"}
              </div>
            </div>
            {selected.start_line || selected.end_line ? (
              <div>
                <div className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-mute mb-1">
                  lines
                </div>
                <div className="font-mono text-sm text-ink tabular-nums">
                  {selected.start_line ?? "?"} – {selected.end_line ?? "?"}
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center gap-3 text-ink-mute">
            <pre className="font-mono text-[0.7rem] leading-tight select-none">
              {`  ·   ·\n·  [ ]\n  ·`}
            </pre>
            <p className="text-xs font-mono uppercase tracking-wider">
              tap a node
            </p>
          </div>
        )}
      </aside>
    </div>
  );
}
