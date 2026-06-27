import { useState } from "react";
import { useAuditLog } from "./useAuditLog.ts";
import { sanitizeText } from "../../lib/sanitize.ts";

/**
 * AuditLog — the read-only "Audit" admin view. Paginated table of governed-action
 * audit rows from the compliance-gated `GET /v1/audit`, with a chain-verify badge that
 * reflects the global hash-chain integrity flag (tamper-evidence made visible).
 */
export function AuditLog() {
  const [page, setPage] = useState(0);
  const size = 25;
  const { data, isLoading, isError, error } = useAuditLog(page, size);

  if (isLoading) return <p className="text-sm text-slate-500">Loading audit log…</p>;
  if (isError || !data) {
    return (
      <p role="alert" className="text-sm text-red-700">
        Could not load the audit log{error instanceof Error ? `: ${error.message}` : ""}.
      </p>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.size));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span
          className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${
            data.chainVerified ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"
          }`}
        >
          {data.chainVerified ? "chain verified" : "chain broken"}
        </span>
        <span className="text-xs text-slate-500">{data.total} rows</span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2">seq</th>
              <th className="px-3 py-2">time</th>
              <th className="px-3 py-2">run</th>
              <th className="px-3 py-2">tool</th>
              <th className="px-3 py-2">phase</th>
              <th className="px-3 py-2">caller</th>
              <th className="px-3 py-2">clearance</th>
              <th className="px-3 py-2">result</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.seq} className="border-t border-slate-100">
                <td className="px-3 py-2 font-mono">{row.seq}</td>
                <td className="px-3 py-2 text-slate-500">{new Date(row.ts).toLocaleString()}</td>
                <td className="px-3 py-2 font-mono text-xs">{sanitizeText(row.runId)}</td>
                <td className="px-3 py-2">{sanitizeText(row.tool)}</td>
                <td className="px-3 py-2">{sanitizeText(row.phase)}</td>
                <td className="px-3 py-2">{sanitizeText(row.caller)}</td>
                <td className="px-3 py-2">{sanitizeText(row.clearance)}</td>
                <td className="px-3 py-2 font-mono text-xs">
                  {sanitizeText(row.resultRef ?? "—")}
                </td>
              </tr>
            ))}
            {data.rows.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-4 text-center text-slate-400">
                  No audit rows.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm">
        <button
          type="button"
          onClick={() => setPage((p) => Math.max(0, p - 1))}
          disabled={page === 0}
          className="rounded border border-slate-300 px-3 py-1 disabled:opacity-50"
        >
          Previous
        </button>
        <span className="text-slate-500">
          Page {page + 1} of {totalPages}
        </span>
        <button
          type="button"
          onClick={() => setPage((p) => p + 1)}
          disabled={page + 1 >= totalPages}
          className="rounded border border-slate-300 px-3 py-1 disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}
