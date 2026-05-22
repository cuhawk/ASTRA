import type { HTMLAttributes, ReactNode } from "react";

interface Props extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function Card({ className = "", children, ...rest }: Props) {
  return (
    <div
      className={`border border-zinc-800 bg-zinc-900 rounded-lg p-6 ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}
