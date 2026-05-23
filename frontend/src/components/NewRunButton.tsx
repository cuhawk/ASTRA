"use client";

import { useState } from "react";
import { NewRunModal } from "./NewRunModal";

export function NewRunButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 bg-accent text-void px-4 py-2 rounded-md font-mono text-xs uppercase tracking-wider hover:bg-accent/90 glow-accent-sm hover:glow-accent active:translate-y-px transition-all"
      >
        <span className="text-sm leading-none">+</span> new run
      </button>
      <NewRunModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
