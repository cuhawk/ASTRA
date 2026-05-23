import type { HTMLAttributes, ReactNode } from "react";

interface Props extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  padded?: boolean;
  hover?: boolean;
}

export function Card({
  className = "",
  children,
  padded = true,
  hover = false,
  ...rest
}: Props) {
  return (
    <div
      className={`relative rounded-lg bg-panel/80 card-inset ${
        hover ? "card-inset-hover transition-shadow" : ""
      } ${padded ? "p-6" : ""} ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

export function SectionHeader({
  eyebrow,
  title,
  right,
}: {
  eyebrow?: string;
  title: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="flex items-end justify-between gap-4 mb-4">
      <div className="flex flex-col gap-1">
        {eyebrow ? (
          <span className="font-mono text-[0.65rem] uppercase tracking-[0.22em] text-ink-mute">
            {eyebrow}
          </span>
        ) : null}
        <h2 className="text-xl font-semibold tracking-tight text-ink">
          {title}
        </h2>
      </div>
      {right ? <div className="flex items-center gap-2">{right}</div> : null}
    </div>
  );
}
