/**
 * Inline SVG callgraph visualization for the landing hero.
 * Pure CSS animation; nodes pulse and edges draw on mount.
 */
export function HeroGraph({ className = "" }: { className?: string }) {
  // Node positions roughly mirror a force-directed callgraph layout.
  const nodes = [
    { id: "n1", x: 60, y: 80, r: 5, hue: "accent", label: "router" },
    { id: "n2", x: 130, y: 50, r: 4, hue: "accent" },
    { id: "n3", x: 200, y: 90, r: 6, hue: "cyan", label: "fetch" },
    { id: "n4", x: 250, y: 150, r: 4.5, hue: "cyan" },
    { id: "n5", x: 180, y: 200, r: 5, hue: "accent" },
    { id: "n6", x: 100, y: 180, r: 4, hue: "accent" },
    { id: "n7", x: 60, y: 140, r: 3.5, hue: "accent" },
    { id: "n8", x: 310, y: 100, r: 4.5, hue: "danger", label: "innerHTML" },
    { id: "n9", x: 290, y: 200, r: 4, hue: "danger" },
    { id: "n10", x: 220, y: 240, r: 3.5, hue: "cyan" },
  ];

  const edges: [string, string, number][] = [
    ["n1", "n2", 0.1],
    ["n2", "n3", 0.2],
    ["n3", "n4", 0.3],
    ["n4", "n5", 0.45],
    ["n5", "n6", 0.55],
    ["n6", "n7", 0.65],
    ["n7", "n1", 0.75],
    ["n3", "n8", 0.85],
    ["n8", "n9", 1.0],
    ["n9", "n10", 1.15],
    ["n4", "n9", 1.3],
    ["n6", "n5", 1.45],
  ];

  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));

  const colorFor = (hue: string) =>
    hue === "accent"
      ? "#10b981"
      : hue === "cyan"
        ? "#06b6d4"
        : hue === "danger"
          ? "#f43f5e"
          : "#10b981";

  return (
    <svg
      viewBox="0 0 360 280"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      <defs>
        <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(16,185,129,0.4)" />
          <stop offset="100%" stopColor="rgba(16,185,129,0)" />
        </radialGradient>
        <filter id="softGlow">
          <feGaussianBlur stdDeviation="1.5" />
        </filter>
      </defs>

      {/* Edges */}
      <g stroke="#10b981" strokeWidth="0.8" fill="none" opacity="0.6">
        {edges.map(([a, b, delay], i) => {
          const A = byId[a];
          const B = byId[b];
          return (
            <line
              key={i}
              x1={A.x}
              y1={A.y}
              x2={B.x}
              y2={B.y}
              className="edge-draw"
              style={{ animationDelay: `${delay}s` }}
              stroke={colorFor(B.hue)}
              opacity={0.45}
            />
          );
        })}
      </g>

      {/* Nodes */}
      <g>
        {nodes.map((n, i) => {
          const c = colorFor(n.hue);
          return (
            <g key={n.id}>
              <circle
                cx={n.x}
                cy={n.y}
                r={n.r * 3}
                fill={c}
                opacity="0.08"
                filter="url(#softGlow)"
              />
              <circle
                cx={n.x}
                cy={n.y}
                r={n.r}
                fill={c}
                className="node-sparkle"
                style={{ animationDelay: `${i * 0.18}s` }}
              />
            </g>
          );
        })}
      </g>

      {/* Labels for a few nodes */}
      <g
        fontFamily="var(--font-jetbrains), ui-monospace, monospace"
        fontSize="8"
        fill="rgba(180,200,210,0.55)"
      >
        {nodes
          .filter((n) => n.label)
          .map((n) => (
            <text key={n.id} x={n.x + n.r + 5} y={n.y - 4}>
              {n.label}
            </text>
          ))}
      </g>
    </svg>
  );
}
