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
import { SecurityReport } from "./SecurityReport";

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

interface TreeNode {
  name: string;
  path: string;
  isDir: boolean;
  children: TreeNode[];
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
  const seg = path.split("/").slice(0, 2).join("/");
  const hue = hashHue(seg);
  return `oklch(0.7 0.15 ${(hue % 90) + 150})`;
}

// Custom syntax highlighter helper for JS/TS/JSX
function highlightJS(code: string): string {
  if (!code) return "";
  return code
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\b(const|let|var|function|return|import|export|from|default|class|extends|async|await|try|catch|finally|if|else|for|while|do|switch|case|break|continue|new|this|typeof|instanceof|throw|in|of)\b/g, '<span class="code-keyword">$1</span>')
    .replace(/(['"`])(.*?)\1/g, '<span class="code-string">$1$2$1</span>')
    .replace(/(\/\/.*)/g, '<span class="code-comment">$1</span>')
    .replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="code-comment">$1</span>')
    .replace(/\b(\d+)\b/g, '<span class="code-number">$1</span>')
    .replace(/\b(console|window|document|process|require|module|exports)\b/g, '<span class="code-function">$1</span>');
}

// Build file tree structure from list of flat paths
function buildTree(paths: string[]): TreeNode {
  const root: TreeNode = { name: "Root", path: "", isDir: true, children: [] };
  for (const path of paths) {
    const parts = path.split("/");
    let current = root;
    let currentPath = "";
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      currentPath = currentPath ? `${currentPath}/${part}` : part;
      const isLast = i === parts.length - 1;
      let child = current.children.find((c) => c.name === part);
      if (!child) {
        child = {
          name: part,
          path: currentPath,
          isDir: !isLast,
          children: [],
        };
        current.children.push(child);
      }
      current = child;
    }
  }
  const sortNodes = (node: TreeNode) => {
    node.children.sort((a, b) => {
      if (a.isDir && !b.isDir) return -1;
      if (!a.isDir && b.isDir) return 1;
      return a.name.localeCompare(b.name);
    });
    node.children.forEach(sortNodes);
  };
  sortNodes(root);
  return root;
}

export function GraphViewer({ runId }: { runId: string }) {
  const cyRef = useRef<Core | null>(null);
  const codeContainerRef = useRef<HTMLDivElement | null>(null);

  // Core Data
  const [funcs, setFuncs] = useState<FunctionRow[] | null>(null);
  const [edges, setEdges] = useState<EdgeRow[] | null>(null);
  const [fileList, setFileList] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [totalFuncs, setTotalFuncs] = useState<number | null>(null);

  // UI State Panels
  const [leftPaneOpen, setLeftPaneOpen] = useState(true);
  const [rightPaneOpen, setRightPaneOpen] = useState(true);

  // File Tree & Filter State
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [fileSearch, setFileSearch] = useState("");

  // Graph Viewer Controls & Node Search
  const [hideIsolated, setHideIsolated] = useState(true);
  const [layoutName, setLayoutName] = useState("cose");
  const [nodeSearch, setNodeSearch] = useState("");
  const [showSearchSuggestions, setShowSearchSuggestions] = useState(false);

  // Inspector & Code State
  const [selected, setSelected] = useState<SelectedNode | null>(null);
  const [codeContent, setCodeContent] = useState<string>("");
  const [codeLoading, setCodeLoading] = useState(false);
  const [codeError, setCodeError] = useState<string | null>(null);

  // Load backend files and callgraph
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [fRes, eRes, filesRes] = await Promise.all([
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
          api<string[]>(`/runs/${runId}/files`),
        ]);

        if (cancelled) return;
        setFuncs(fRes.rows);
        setEdges(eRes.rows);
        setFileList(filesRes);

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

  // Load Code Content when a node/file is selected
  useEffect(() => {
    const targetPath = selected?.path || selectedFile;
    if (!targetPath) {
      setCodeContent("");
      return;
    }
    let cancelled = false;
    async function loadFileContent() {
      setCodeLoading(true);
      setCodeError(null);
      try {
        const res = await api<{ content: string }>(
          `/runs/${runId}/files/content?path=${encodeURIComponent(targetPath!)}`
        );
        if (!cancelled) {
          setCodeContent(res.content);
        }
      } catch (err) {
        if (!cancelled) {
          setCodeError("Failed to load source code");
        }
      } finally {
        if (!cancelled) setCodeLoading(false);
      }
    }
    loadFileContent();
    return () => {
      cancelled = true;
    };
  }, [selected?.path, selectedFile, runId]);

  // Scroll to line when selected node changes
  useEffect(() => {
    if (selected && selected.start_line && codeContent && codeContainerRef.current) {
      const startLine = selected.start_line;
      setTimeout(() => {
        const lineEl = codeContainerRef.current?.querySelector(
          `[data-line="${startLine}"]`
        );
        if (lineEl) {
          lineEl.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 100);
    }
  }, [selected, codeContent]);

  // Tree representation
  const treeRoot = useMemo(() => {
    const filtered = fileList.filter((f) =>
      f.toLowerCase().includes(fileSearch.toLowerCase())
    );
    return buildTree(filtered);
  }, [fileList, fileSearch]);

  // Memoized nodes and edges based on filter states
  const elements = useMemo<ElementDefinition[]>(() => {
    if (!funcs || !edges) return [];
    
    // Filter functions by selectedFile path
    let filteredFuncs = funcs;
    if (selectedFile) {
      filteredFuncs = funcs.filter((f) => f.path === selectedFile);
    }

    const ids = new Set(filteredFuncs.map((f) => f.id));
    const filteredEdges = edges.filter(
      (e) => ids.has(e.source) && ids.has(e.target)
    );

    const connected = new Set<string>();
    if (hideIsolated) {
      filteredEdges.forEach((e) => {
        connected.add(e.source);
        connected.add(e.target);
      });
    }

    const visibleFuncs = hideIsolated
      ? filteredFuncs.filter((f) => connected.has(f.id))
      : filteredFuncs;

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
          (connected.has(e.source) && connected.has(e.target))
      )
      .map((e, i) => ({
        data: { id: `e${i}`, source: e.source, target: e.target },
      }));

    return [...nodes, ...edgeEls];
  }, [funcs, edges, hideIsolated, selectedFile]);

  // Autocomplete Suggestions matching nodeSearch
  const searchSuggestions = useMemo(() => {
    if (!nodeSearch || !funcs) return [];
    return funcs
      .filter((f) => (f.name ?? "").toLowerCase().includes(nodeSearch.toLowerCase()))
      .slice(0, 10);
  }, [nodeSearch, funcs]);

  // Cytoscape styles
  const stylesheet = useMemo<StylesheetCSS[]>(
    () => [
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
    ] as unknown as StylesheetCSS[],
    []
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
      name: layoutName,
      animate: true,
      animationDuration: 300,
      nodeRepulsion: 8000,
      idealEdgeLength: 60,
      gravity: 0.25,
      numIter: 1200,
      randomize: true,
      fit: true,
      padding: 30,
    }),
    [layoutName]
  );

  // Cytoscape Viewport Helpers
  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.2);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() / 1.2);
  const handleFit = () => cyRef.current?.fit();
  const handleCenter = () => cyRef.current?.center();

  // Jump to specific function from autocomplete
  const handleJumpToNode = (fn: FunctionRow) => {
    setNodeSearch("");
    setShowSearchSuggestions(false);
    
    // Select path/file tree filter
    if (fn.path) {
      setSelectedFile(fn.path);
    }
    
    setTimeout(() => {
      const cy = cyRef.current;
      if (!cy) return;
      const node = cy.getElementById(fn.id);
      if (node.length > 0) {
        cy.$(":selected").unselect();
        node.select();
        cy.animate({
          center: { eles: node },
          zoom: 2.2,
          duration: 350,
        });
        setSelected({
          id: fn.id,
          name: fn.name,
          path: fn.path,
          start_line: fn.start_line,
          end_line: fn.end_line,
        });
      }
    }, 100);
  };

  // Toggle path expansions
  const toggleExpand = (path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  // Render tree node recursive component
  const renderTreeNode = (node: TreeNode, depth = 0) => {
    if (node.path === "" && node.children.length === 0) {
      return <div className="text-ink-mute text-xs px-2">No files matching filter</div>;
    }
    return (
      <div key={node.path || "root"}>
        {node.path !== "" && (
          <div
            className={`flex items-center justify-between text-xs font-mono py-1.5 px-2 rounded cursor-pointer transition select-none ${
              selectedFile === node.path
                ? "bg-accent/15 text-accent border border-accent/25"
                : "text-ink-dim hover:bg-elev/40 hover:text-ink"
            }`}
            style={{ paddingLeft: `${depth * 10 + 6}px` }}
            onClick={() => {
              if (node.isDir) {
                toggleExpand(node.path);
              } else {
                setSelectedFile(node.path);
              }
            }}
          >
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-ink-mute font-bold shrink-0">
                {node.isDir ? (expandedPaths.has(node.path) ? "▾" : "▸") : "•"}
              </span>
              <span className="truncate">{node.name}</span>
            </div>
            {node.isDir && (
              <span className="text-[0.6rem] text-ink-mute px-1 py-0.25 bg-void/50 rounded border border-hair/30">
                {node.children.length}
              </span>
            )}
          </div>
        )}
        {(node.path === "" || expandedPaths.has(node.path)) && (
          <div className="flex flex-col gap-0.5 mt-0.5">
            {node.children.map((child) => renderTreeNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  if (error) {
    return (
      <div className="rounded-lg border border-rose-700/60 bg-rose-950/30 p-6 text-rose-300 font-mono text-sm whitespace-pre-wrap">
        graph load failed: {error}
      </div>
    );
  }

  if (loading || !funcs || !edges) {
    return (
      <div className="h-full flex items-center justify-center text-ink-mute font-mono text-sm">
        <span className="inline-flex items-center gap-3">
          <span className="inline-block w-3 h-3 border-2 border-accent border-t-transparent rounded-full orbit" />
          materializing callgraph…
        </span>
      </div>
    );
  }
  const visibleNodeCount = elements.filter((e) => !("source" in (e.data ?? {}))).length;
  const visibleEdgeCount = elements.length - visibleNodeCount;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[240px_1fr_340px] lg:grid-cols-[210px_1fr_300px] gap-3 h-full min-h-[500px] p-2 md:p-3 relative bg-grid">
      {/* 1. LEFT PANEL: Reconstructed File Tree */}
      <aside
        className={`${
          leftPaneOpen ? "flex" : "hidden"
        } flex-col gap-2 p-3 rounded-lg bg-panel card-inset overflow-hidden h-full min-h-0`}
      >
        <div className="flex items-center justify-between shrink-0">
          <span className="font-mono text-[0.62rem] uppercase tracking-[0.24em] text-ink-mute">
            file tree
          </span>
          <button
            onClick={() => setSelectedFile(null)}
            className="text-[0.62rem] font-mono uppercase tracking-wider text-ink-mute hover:text-accent disabled:opacity-50"
            disabled={!selectedFile}
          >
            clear filter
          </button>
        </div>

        <input
          type="text"
          value={fileSearch}
          onChange={(e) => setFileSearch(e.target.value)}
          placeholder="Filter tree..."
          className="w-full bg-void/60 border border-hair rounded px-2.5 py-1.5 font-mono text-xs text-ink placeholder:text-ink-mute focus-phosphor"
        />

        <div className="flex-1 overflow-y-auto pr-1">
          {renderTreeNode(treeRoot, -1)}
        </div>
      </aside>

      {/* Pane togglers for maximum screen space */}
      <button
        onClick={() => setLeftPaneOpen(!leftPaneOpen)}
        className="absolute left-[-10px] top-[48%] z-20 w-5 h-8 bg-panel border border-hair rounded-md flex items-center justify-center text-[0.55rem] font-mono text-ink-mute hover:text-accent hover:border-accent/50 cursor-pointer shadow-md select-none hidden lg:flex hover-lift focus-phosphor"
      >
        {leftPaneOpen ? "◀" : "▶"}
      </button>

      {/* 2. CENTER PANEL: Callgraph Viewport & Toolbar */}
      <div className="flex flex-col gap-3 h-full min-w-0">
        {/* Controls Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-panel card-inset rounded-lg shrink-0">
          <div className="flex items-center gap-1">
            <button
              onClick={handleZoomIn}
              className="px-2.5 py-1 rounded bg-void border border-hair/85 hover:border-accent/50 hover:text-accent text-xs font-mono transition hover-lift focus-phosphor"
              title="Zoom In"
            >
              +
            </button>
            <button
              onClick={handleZoomOut}
              className="px-2.5 py-1 rounded bg-void border border-hair/85 hover:border-accent/50 hover:text-accent text-xs font-mono transition hover-lift focus-phosphor"
              title="Zoom Out"
            >
              -
            </button>
            <button
              onClick={handleFit}
              className="px-2.5 py-1 rounded bg-void border border-hair/85 hover:border-accent/50 hover:text-accent text-xs font-mono transition"
              title="Fit to Screen"
            >
              fit
            </button>
            <button
              onClick={handleCenter}
              className="px-2.5 py-1 rounded bg-void border border-hair/85 hover:border-accent/50 hover:text-accent text-xs font-mono transition"
              title="Center View"
            >
              center
            </button>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-[0.62rem] font-mono uppercase text-ink-mute">layout</label>
            <select
              value={layoutName}
              onChange={(e) => {
                setLayoutName(e.target.value);
                setTimeout(() => cyRef.current?.layout({ ...layout, name: e.target.value }).run(), 100);
              }}
              className="bg-void border border-hair/80 rounded px-2 py-1 text-xs font-mono text-ink-dim focus:outline-none focus:border-accent/40"
            >
              <option value="cose">cose</option>
              <option value="concentric">concentric</option>
              <option value="grid">grid</option>
              <option value="circle">circle</option>
              <option value="breadthfirst">breadthfirst</option>
            </select>
          </div>

          {/* Autocomplete Node Search */}
          <div className="relative w-44 md:w-56">
            <input
              type="text"
              value={nodeSearch}
              onChange={(e) => {
                setNodeSearch(e.target.value);
                setShowSearchSuggestions(true);
              }}
              onFocus={() => setShowSearchSuggestions(true)}
              onBlur={() => setTimeout(() => setShowSearchSuggestions(false), 200)}
              placeholder="Search function..."
              className="w-full bg-void/60 border border-hair rounded px-2.5 py-1 font-mono text-xs text-ink placeholder:text-ink-mute focus:outline-none focus:border-accent/40"
            />
            {showSearchSuggestions && searchSuggestions.length > 0 && (
              <div className="absolute top-full left-0 right-0 z-30 mt-1 bg-void border border-hair rounded-md shadow-lg max-h-40 overflow-y-auto font-mono text-xs divide-y divide-hair/40">
                {searchSuggestions.map((fn) => (
                  <div
                    key={fn.id}
                    onClick={() => handleJumpToNode(fn)}
                    className="p-2 cursor-pointer hover:bg-elev/60 hover:text-accent truncate"
                  >
                    {fn.name || fn.id}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Canvas Area */}
        <div className="relative flex-1 rounded-lg bg-panel card-inset overflow-hidden min-h-0">
          <div className="absolute top-3 left-3 z-10 flex flex-wrap items-center gap-2 pointer-events-none">
            <span className="pointer-events-auto inline-flex items-center gap-2 px-2.5 py-1 rounded bg-void/85 border border-hair/70 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-ink-mute">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent" />
              nodes <span className="text-ink-dim tabular-nums">{visibleNodeCount}</span>
              <span className="text-hair-bright">·</span>
              edges{" "}
              <span className="text-ink-dim tabular-nums">{visibleEdgeCount}</span>
            </span>
            {totalFuncs !== null && totalFuncs > funcs.length ? (
              <span className="pointer-events-auto inline-flex items-center gap-2 px-2.5 py-1 rounded bg-amber-950/40 border border-amber-700/40 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-amber-300">
                showing first 500 of{" "}
                <span className="tabular-nums">{totalFuncs}</span>
              </span>
            ) : null}
          </div>

          <div className="absolute top-3 right-3 z-10">
            <label className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-void/85 border border-hair/70 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-ink-dim cursor-pointer hover:text-accent transition">
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
            style={{ width: "100%", height: "100%" }}
          />
        </div>
      </div>

      <button
        onClick={() => setRightPaneOpen(!rightPaneOpen)}
        className="absolute right-[-10px] top-[48%] z-20 w-5 h-8 bg-panel border border-hair rounded-md flex items-center justify-center text-[0.55rem] font-mono text-ink-mute hover:text-accent hover:border-accent/50 cursor-pointer shadow-md select-none hidden lg:flex hover-lift focus-phosphor"
      >
        {rightPaneOpen ? "▶" : "◀"}
      </button>

      {/* 3. RIGHT COLUMN: Inspector (top) + Security Report (bottom) */}
      <div
        className={`${rightPaneOpen ? "grid" : "hidden"} grid-rows-[minmax(0,1.1fr)_minmax(0,1fr)] gap-3 h-full min-h-0`}
      >
      <aside
        className="rounded-lg bg-panel card-inset p-4 flex flex-col gap-3 overflow-hidden min-h-0"
      >
        <div className="flex items-center justify-between shrink-0">
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.24em] text-ink-mute">
            inspector
          </span>
          {selected && (
            <button
              onClick={() => {
                setSelected(null);
                cyRef.current?.$(":selected").unselect();
              }}
              className="font-mono text-[0.62rem] uppercase tracking-wider text-ink-mute hover:text-accent"
            >
              clear
            </button>
          )}
        </div>

        {selected ? (
          <div className="flex-1 flex flex-col gap-3 overflow-hidden min-h-0">
            {/* Metadata info */}
            <div className="grid grid-cols-2 gap-2 text-xs font-mono shrink-0">
              <div className="p-2 bg-void/50 rounded border border-hair/30">
                <div className="text-[0.55rem] uppercase text-ink-mute mb-0.5">name</div>
                <div className="text-accent truncate" title={selected.name ?? ""}>
                  {selected.name ?? "—"}
                </div>
              </div>
              <div className="p-2 bg-void/50 rounded border border-hair/30">
                <div className="text-[0.55rem] uppercase text-ink-mute mb-0.5">lines</div>
                <div className="text-ink-dim tabular-nums">
                  {selected.start_line ?? "?"} – {selected.end_line ?? "?"}
                </div>
              </div>
            </div>

            <div className="text-[0.55rem] font-mono uppercase text-ink-mute shrink-0">
              file: <span className="text-ink-dim normal-case break-all">{selected.path || "—"}</span>
            </div>

            {/* Code snippets area */}
            <div className="flex-1 rounded bg-void/70 border border-hair/80 flex flex-col overflow-hidden min-h-0">
              <div className="flex items-center justify-between px-3 py-1.5 border-b border-hair/60 bg-elev/30 shrink-0">
                <span className="font-mono text-[0.55rem] uppercase text-ink-mute">source preview</span>
                {selected.path && (
                  <span className="font-mono text-[0.55rem] text-accent-2 select-all">
                    {selected.path.split("/").pop()}
                  </span>
                )}
              </div>

              <div
                ref={codeContainerRef}
                className="flex-1 overflow-auto py-2 font-mono text-xs select-text"
              >
                {codeLoading ? (
                  <div className="h-full flex items-center justify-center text-ink-mute">
                    <span className="inline-block w-2.5 h-2.5 border-2 border-accent border-t-transparent rounded-full orbit mr-2" />
                    fetching file...
                  </div>
                ) : codeError ? (
                  <div className="p-3 text-rose-300 text-[0.7rem]">{codeError}</div>
                ) : codeContent ? (
                  <pre className="inline-block min-w-full">
                    {renderCodeLines(codeContent, selected.start_line ?? null, selected.end_line ?? null)}
                  </pre>
                ) : (
                  <div className="p-3 text-ink-mute text-center text-[0.7rem]">Empty source file</div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center gap-3 text-ink-mute">
            <pre className="font-mono text-[0.7rem] leading-tight select-none">
              {`  ·   ·\n·  [ ]\n  ·`}
            </pre>
            <p className="text-xs font-mono uppercase tracking-wider">
              tap a node to inspect code
            </p>
          </div>
        )}
      </aside>

        <SecurityReport />
      </div>
    </div>
  );
}

// Render lines of the code content with highlight span wraps
function renderCodeLines(
  content: string,
  startLine: number | null,
  endLine: number | null
) {
  const lines = content.split("\n");
  return lines.map((line, index) => {
    const lineNum = index + 1;
    const isHighlighted =
      startLine !== null &&
      endLine !== null &&
      lineNum >= startLine &&
      lineNum <= endLine;

    const highlightedText = highlightJS(line);

    return (
      <div
        key={index}
        data-line={lineNum}
        className={isHighlighted ? "code-highlight-line" : "code-line"}
      >
        <span className="inline-block w-8 text-right pr-2 text-[0.65rem] select-none text-ink-mute border-r border-hair mr-2">
          {lineNum}
        </span>
        <code
          dangerouslySetInnerHTML={{ __html: highlightedText || "&nbsp;" }}
          className="font-mono text-xs text-ink-dim"
        />
      </div>
    );
  });
}
