import { useState } from "react";
import { EvalScores } from "./EvalScores.tsx";
import { CostDashboard } from "./CostDashboard.tsx";
import { AuditLog } from "./AuditLog.tsx";
import { useClearance } from "../auth/useClearance.ts";

type Tab = "evals" | "cost" | "audit";

const TABS: { id: Tab; label: string }[] = [
  { id: "evals", label: "Evals" },
  { id: "cost", label: "Cost" },
  { id: "audit", label: "Audit" },
];

/**
 * AdminPage — the read-only admin area (Evals | Cost | Audit). Clearance-gated to
 * compliance+ (UX gate; the route guard + every backend re-enforce server-side). No
 * mutable admin actions exist (view-only by design — D-P5-3 / ADR-0053).
 */
export function AdminPage() {
  const [tab, setTab] = useState<Tab>("evals");
  const { hasAtLeast } = useClearance();

  // Defensive UX guard (the route already restricts /admin to compliance+).
  if (!hasAtLeast("compliance")) {
    return <p className="text-sm text-slate-600">You do not have access to the admin area.</p>;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h2 className="text-lg font-semibold">Admin (read-only)</h2>
      <nav className="flex gap-1 border-b border-slate-200" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t.id
                ? "border-slate-800 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div role="tabpanel">
        {tab === "evals" && <EvalScores />}
        {tab === "cost" && <CostDashboard />}
        {tab === "audit" && <AuditLog />}
      </div>
    </div>
  );
}
