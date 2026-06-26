import { useState } from "react";
import type { TraceStep } from "../../lib/types.ts";

/**
 * TracePanel — the collapsible execution trace (NIST AI RMF traceability made visible).
 * Renders the planner→retrieve→assess→approve→act timeline; each step shows its
 * node-specific flags (breach / approved / citations count / error) as small badges.
 */
function stepBadges(step: TraceStep): string[] {
  const badges: string[] = [];
  if (typeof step.breach === "boolean") badges.push(step.breach ? "breach" : "no breach");
  if (typeof step.ambiguous === "boolean" && step.ambiguous) badges.push("ambiguous");
  if (typeof step.approved === "boolean") badges.push(step.approved ? "approved" : "rejected");
  if (typeof step.citations === "number") badges.push(`${step.citations} citations`);
  if (typeof step.error === "string") badges.push("error");
  return badges;
}

export function TracePanel({ trace = [] }: { trace?: TraceStep[] }) {
  const [open, setOpen] = useState(false);
  if (trace.length === 0) return null;

  return (
    <div className="mt-3 border-t border-slate-100 pt-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="text-xs font-medium text-slate-600 hover:underline"
      >
        {open ? "▾" : "▸"} Execution trace ({trace.length} steps)
      </button>
      {open && (
        <ol className="mt-2 space-y-1" data-testid="trace-steps">
          {trace.map((step, i) => (
            <li key={i} className="flex items-center gap-2 text-xs">
              <span className="font-mono text-slate-400">{i + 1}.</span>
              <span className="font-medium text-slate-700">{String(step.node)}</span>
              {stepBadges(step).map((b) => (
                <span
                  key={b}
                  className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600"
                >
                  {b}
                </span>
              ))}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
