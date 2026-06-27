import { useStaticJson } from "./useStaticJson.ts";
import type { EvalSummary } from "../../lib/types.ts";

function PassBadge({ passed }: { passed: boolean }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${
        passed ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"
      }`}
    >
      {passed ? "PASS" : "FAIL"}
    </span>
  );
}

function fmt(value: number | null | undefined, digits = 3): string {
  return value == null ? "—" : value.toFixed(digits);
}

function pct(value: number | null | undefined): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-1.5 text-sm last:border-0">
      <span className="text-slate-600">{label}</span>
      <span className="font-mono text-slate-900">{value}</span>
    </div>
  );
}

/**
 * EvalScores — the read-only "Evals" admin view. Renders the committed eval-summary
 * snapshot (the REAL P2 RAG gate + P4 agent gate results); the UI never runs an eval.
 */
export function EvalScores() {
  const { data, isLoading, isError } = useStaticJson<EvalSummary>(
    "/eval-summary.json",
    "eval-summary",
  );

  if (isLoading) return <p className="text-sm text-slate-500">Loading eval scores…</p>;
  if (isError || !data) {
    return (
      <p className="text-sm text-slate-500">
        Eval summary not available. Generate it with{" "}
        <code className="rounded bg-slate-100 px-1">evals/scripts/refresh_eval_summary.py</code>.
      </p>
    );
  }

  const { rag, agent } = data;

  return (
    <div className="space-y-6">
      <p className="text-xs text-slate-500">
        Snapshot of the committed gate artifact · git {data.gitSha} · generated{" "}
        {new Date(data.generatedAt).toLocaleString()}
      </p>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <header className="mb-2 flex items-center justify-between">
          <h3 className="font-medium">RAG gate (RAGAS + adversarial)</h3>
          <PassBadge passed={rag.passed} />
        </header>
        <MetricRow label="Faithfulness" value={fmt(rag.scores.faithfulness)} />
        <MetricRow label="Answer relevancy" value={fmt(rag.scores.answerRelevancy)} />
        <MetricRow label="Context precision" value={fmt(rag.scores.contextPrecision)} />
        <MetricRow label="Context recall" value={fmt(rag.scores.contextRecall)} />
        <MetricRow label="Citation correctness" value={fmt(rag.scores.citationCorrectness)} />
        <MetricRow label="Adversarial pass-rate" value={pct(rag.adversarialPassRate)} />
        <MetricRow label="Samples" value={String(rag.nSamples ?? "—")} />
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <header className="mb-2 flex items-center justify-between">
          <h3 className="font-medium">Agent gate (trajectory + safety)</h3>
          <PassBadge passed={agent.passed} />
        </header>
        <MetricRow label="Scenarios" value={String(agent.scenarios ?? "—")} />
        <MetricRow label="Task success" value={pct(agent.taskSuccessRate)} />
        <MetricRow label="Tool selection" value={pct(agent.toolSelectionRate)} />
        <MetricRow label="Argument correctness" value={pct(agent.argumentCorrectnessRate)} />
        <MetricRow label="HITL respected" value={agent.hitlRespected ? "yes" : "NO"} />
        <MetricRow
          label="Authorization respected"
          value={agent.authorizationRespected ? "yes" : "NO"}
        />
        <MetricRow label="Unapproved writes" value={String(agent.unapprovedWrites ?? "—")} />
        <MetricRow label="Unauthorized writes" value={String(agent.unauthorizedWrites ?? "—")} />
      </section>
    </div>
  );
}
