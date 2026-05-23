interface Props {
  className?: string;
}

/**
 * ASTRA wordmark — a monospaced lock-up with a small constellation glyph
 * to the left, evoking nodes-and-edges. Currentcolor driven for theming.
 */
export function Wordmark({ className = "h-5 w-auto" }: Props) {
  return (
    <svg
      viewBox="0 0 132 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="ASTRA"
    >
      {/* constellation: 3 nodes + 2 edges, ~16px wide */}
      <g stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
        <line x1="4" y1="6" x2="13" y2="12" opacity="0.7" />
        <line x1="13" y1="12" x2="6" y2="18" opacity="0.7" />
      </g>
      <g fill="currentColor">
        <circle cx="4" cy="6" r="2" />
        <circle cx="13" cy="12" r="2.4" />
        <circle cx="6" cy="18" r="1.6" opacity="0.8" />
      </g>
      {/* wordmark */}
      <text
        x="24"
        y="17"
        fontFamily="var(--font-jetbrains), ui-monospace, monospace"
        fontSize="14"
        fontWeight="700"
        letterSpacing="0.16em"
        fill="currentColor"
      >
        ASTRA
      </text>
    </svg>
  );
}
