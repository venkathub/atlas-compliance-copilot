import { useEffect, useMemo, useRef } from "react";
import { Answer } from "./Answer.tsx";
import { ApprovalCard } from "./ApprovalCard.tsx";
import { TracePanel } from "./TracePanel.tsx";
import { useAgentRun } from "./useAgentRun.ts";
import { adaptAgentCitations } from "./agentCitations.ts";
import { sanitizeText } from "../../lib/sanitize.ts";

/**
 * AgentRunView — one governed-action run, end to end: the cited answer, the HITL
 * ApprovalCard (when AWAITING_APPROVAL), the terminal result (draft SAR ref on
 * COMPLETED; rejected/failed otherwise), and the collapsible execution trace.
 *
 * The run is started once on mount. The component never constructs a write — it only
 * forwards the human's Approve/Reject (via useAgentRun.resume) to the agent.
 */
export function AgentRunView({
  query,
  account,
  period,
}: {
  query: string;
  account: string;
  period: string;
}) {
  const { run, error, busy, start, resume } = useAgentRun();
  const request = useMemo(() => ({ query, account, period }), [query, account, period]);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void start(request);
  }, [start, request]);

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2">
        <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-700">
          AI-generated
        </span>
        <span className="text-xs text-slate-500">
          Governed action · {sanitizeText(account)} · {sanitizeText(period)}
        </span>
        {busy && <span className="text-xs text-slate-400">working…</span>}
      </div>

      {run?.answer && (
        <Answer markdown={run.answer} citations={adaptAgentCitations(run.citations)} />
      )}

      {run?.status === "AWAITING_APPROVAL" && run.proposedAction && (
        <ApprovalCard
          action={run.proposedAction}
          busy={busy}
          onDecision={(approved, note) => void resume(approved, note)}
        />
      )}

      {run?.status === "AWAITING_CLARIFICATION" && (
        <p className="text-sm text-amber-800">The agent needs clarification to proceed.</p>
      )}

      {run?.status === "COMPLETED" && run.action?.draftRef && (
        <div
          data-testid="draft-result"
          className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900"
        >
          Draft SAR created:{" "}
          <strong className="font-mono">{sanitizeText(run.action.draftRef)}</strong>{" "}
          <span className="text-emerald-700">
            (status {sanitizeText(run.action.status ?? "DRAFT")})
          </span>
          {run.auditRef && (
            <span className="mt-1 block text-xs text-emerald-700">
              Audit ref: {sanitizeText(run.auditRef)}
            </span>
          )}
        </div>
      )}

      {run?.status === "REJECTED" && (
        <p className="text-sm text-slate-600">Action rejected — no draft was created.</p>
      )}

      {run?.status === "FAILED" && (
        <p role="alert" className="text-sm text-red-700">
          The governed action failed; no draft was created.
        </p>
      )}

      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}

      <TracePanel trace={run?.trace} />
    </div>
  );
}
