import { useStaticJson } from "./useStaticJson.ts";
import type { CostSummary } from "../../lib/types.ts";

// Public, build-time-injected Grafana embed config (no secret). When unset, the cost
// dashboard degrades to a deep-link/placeholder rather than embedding nothing.
const GRAFANA_URL = import.meta.env.VITE_GRAFANA_URL ?? "";
const COST_UID = import.meta.env.VITE_GRAFANA_COST_DASHBOARD_UID ?? "atlas-cost-p3";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-2xl font-semibold text-slate-900">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

/**
 * CostDashboard — the read-only "Cost" admin view. The always-on NATIVE summary is the
 * committed P3 cost-reduction headline (cost-summary.json); the live drill-down is the
 * securely-embedded Grafana cost dashboard (uid atlas-cost-p3). Secure-embed hardening
 * (allow_embedding + CSP frame-ancestors / share token, G-P5-3) is wired at the proxy
 * (Task 7/8); here the embed URL is env-driven with a graceful fallback.
 */
export function CostDashboard() {
  const { data, isLoading, isError } = useStaticJson<CostSummary>(
    "/cost-summary.json",
    "cost-summary",
  );

  const embedUrl = GRAFANA_URL ? `${GRAFANA_URL}/d/${COST_UID}?kiosk&theme=light` : null;

  return (
    <div className="space-y-6">
      <section>
        <h3 className="mb-2 font-medium">Cost reduction (P3 cache + routing)</h3>
        {isLoading && <p className="text-sm text-slate-500">Loading cost summary…</p>}
        {(isError || !data) && !isLoading && (
          <p className="text-sm text-slate-500">
            Cost summary not available. Generate it with{" "}
            <code className="rounded bg-slate-100 px-1">evals/scripts/refresh_eval_summary.py</code>
            .
          </p>
        )}
        {data && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat
              label="Cost reduction"
              value={data.costReductionPct == null ? "—" : `${data.costReductionPct}%`}
            />
            <Stat
              label="Target"
              value={data.targetReductionPct == null ? "—" : `${data.targetReductionPct}%`}
            />
            <Stat label="Meets target" value={data.meetsTarget ? "yes" : "no"} />
            <Stat
              label="Units off → on"
              value={`${data.costOffUnits ?? "—"} → ${data.costOnUnits ?? "—"}`}
            />
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-2 font-medium">Live cost &amp; latency (Grafana)</h3>
        {embedUrl ? (
          <iframe
            title="Atlas cost dashboard"
            src={embedUrl}
            className="h-[480px] w-full rounded-lg border border-slate-200"
          />
        ) : (
          <p className="text-sm text-slate-500">
            Set <code className="rounded bg-slate-100 px-1">VITE_GRAFANA_URL</code> to embed the
            live cost/latency dashboard (uid <code>{COST_UID}</code>).
          </p>
        )}
      </section>
    </div>
  );
}
