import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "ghost";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  children: ReactNode;
}

const base = "px-4 py-2 rounded text-sm font-medium transition-colors";
const styles: Record<Variant, string> = {
  primary: "bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50",
  ghost:
    "border border-zinc-700 text-zinc-100 hover:bg-zinc-800 disabled:opacity-50",
};

export function Button({
  variant = "primary",
  className = "",
  children,
  ...rest
}: Props) {
  return (
    <button className={`${base} ${styles[variant]} ${className}`} {...rest}>
      {children}
    </button>
  );
}
