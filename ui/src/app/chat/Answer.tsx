import type { Citation as CitationType } from "../../lib/types.ts";
import { sanitizeMarkdown } from "../../lib/sanitize.ts";
import { Citation } from "./Citation.tsx";

/**
 * Answer — renders an UNTRUSTED model answer (inline [n]-cited markdown) safely.
 *
 * The markdown is sanitized to an HTML allowlist BEFORE it ever touches the DOM
 * (LLM05); `dangerouslySetInnerHTML` is used ONLY on the already-sanitized string.
 * The "Sources" row exposes each citation as a clickable chip → provenance popover
 * (documentId + clearance + snippet), surfacing the P1/P2 grounding (LLM09).
 *
 * The "AI-generated" message label + session AI disclosure are layered on in Task 3.
 */
export function Answer({
  markdown,
  citations = [],
}: {
  markdown: string;
  citations?: CitationType[];
}) {
  const html = sanitizeMarkdown(markdown);

  return (
    <div className="space-y-3">
      <div
        className="atlas-answer text-slate-800 leading-relaxed [&_a]:text-blue-700 [&_a]:underline [&_code]:rounded [&_code]:bg-slate-100 [&_code]:px-1"
        // Safe: `html` is the output of sanitizeMarkdown (DOMPurify allowlist).
        dangerouslySetInnerHTML={{ __html: html }}
      />
      {citations.length > 0 && (
        <div className="flex flex-wrap items-center gap-1 border-t border-slate-100 pt-2 text-sm">
          <span className="mr-1 text-xs uppercase tracking-wide text-slate-500">Sources</span>
          {citations.map((c) => (
            <Citation key={c.marker} citation={c} />
          ))}
        </div>
      )}
    </div>
  );
}
