import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
}

const base =
  "inline-flex items-center justify-center gap-2 font-mono uppercase tracking-wider rounded-md transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed focus-phosphor select-none";

const sizes: Record<Size, string> = {
  sm: "px-3 py-1.5 text-[0.7rem]",
  md: "px-4 py-2 text-xs",
  lg: "px-6 py-3 text-sm",
};

const styles: Record<Variant, string> = {
  primary:
    "bg-accent text-void hover:bg-accent/90 hover:shadow-[0_0_20px_-4px_rgba(16,185,129,0.6)] active:translate-y-px",
  ghost:
    "border border-hair text-ink-dim hover:text-accent hover:border-accent/60 bg-elev/40 hover:bg-elev/80 active:translate-y-px",
  danger:
    "border border-rose-700/60 bg-rose-950/30 text-rose-300 hover:border-rose-500 hover:bg-rose-950/50",
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  children,
  ...rest
}: Props) {
  return (
    <button
      className={`${base} ${sizes[size]} ${styles[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
