import { useState } from "react";
import type { ProposedAction } from "../../lib/types.ts";
import { sanitizeText } from "../../lib/sanitize.ts";

/**
 * ApprovalCard — the human-in-the-loop checkpoint made visible (LLM06 / ADR HITL).
 *
 * Shows the agent's PROPOSED action (read-only) plus the EU-AI-Act "AI-assisted draft"
 * stamp, and an Approve / Reject control. This card is the *trigger*, not the
 * *authority*: it only forwards the human's decision to the agent's resume endpoint —
 * it NEVER constructs or pre-fills a write call. Rejecting yields no write.
 */
export function ApprovalCard({
  action,
  busy,
  onDecision,
}: {
  action: ProposedAction;
  busy?: boolean;
  onDecision: (approved: boolean, note?: string) => void;
}) {
  const [note, setNote] = useState("");
  const argEntries = Object.entries(action.args ?? {});

  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 p-4">
      <div className="mb-2 flex items-center gap-2">
        <span className="rounded bg-amber-200 px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-amber-900">
          Approval required
        </span>
        <span className="text-xs text-amber-800">AI-assisted draft — requires human review</span>
      </div>

      <p className="text-sm text-slate-800">
        The agent proposes to run{" "}
        <code className="rounded bg-white px-1 font-mono text-slate-900">
          {sanitizeText(action.tool)}
        </code>
        :
      </p>

      <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs">
        {argEntries.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="font-medium text-slate-500">{sanitizeText(k)}</dt>
            <dd className="text-slate-800">{sanitizeText(JSON.stringify(v))}</dd>
          </div>
        ))}
      </dl>

      <label className="mt-3 block text-xs text-slate-600">
        Reviewer note (optional)
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
          placeholder="e.g. Reviewed — consistent with policy"
        />
      </label>

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => onDecision(true, note.trim() || undefined)}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Approve
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onDecision(false, note.trim() || undefined)}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}
