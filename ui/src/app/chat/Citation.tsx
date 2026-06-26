import { useState } from "react";
import type { Citation as CitationType } from "../../lib/types.ts";
import { sanitizeText } from "../../lib/sanitize.ts";
import { clearanceLabel } from "../auth/clearance.ts";

/**
 * Citation — a clickable [n] chip that reveals the source's provenance (LLM09:
 * grounding made visible). The popover shows the documentId, the source's clearance,
 * and the snippet. The snippet is UNTRUSTED, so it is text-sanitized AND rendered as
 * a React text node (no innerHTML) — doubly inert (LLM05).
 */
export function Citation({ citation }: { citation: CitationType }) {
  const [open, setOpen] = useState(false);
  const popoverId = `citation-${citation.n}-popover`;

  return (
    <span className="relative inline-block align-baseline">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={popoverId}
        className="mx-0.5 rounded bg-slate-200 px-1.5 text-xs font-medium text-slate-700 hover:bg-slate-300"
      >
        [{citation.n}]
      </button>
      {open && (
        <span
          id={popoverId}
          role="dialog"
          aria-label={`Source ${citation.n}`}
          className="absolute z-10 mt-1 block w-72 rounded-md border border-slate-200 bg-white p-3 text-left text-xs shadow-lg"
        >
          <span className="block font-mono text-slate-800">
            {sanitizeText(citation.documentId)}
          </span>
          <span className="mt-1 block text-slate-500">
            Clearance: {clearanceLabel(citation.clearance)}
          </span>
          <span className="mt-2 block text-slate-700">{sanitizeText(citation.snippet)}</span>
        </span>
      )}
    </span>
  );
}
