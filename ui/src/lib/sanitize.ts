/**
 * sanitize — the LLM05 render-boundary defense (STUB for Task 0).
 *
 * Model/markdown output (answers, citations, rationales, audit rows) is UNTRUSTED.
 * The full implementation (Task 2) renders markdown → HTML and runs it through a
 * DOMPurify allowlist: no <script>, no event handlers, no javascript:/data: URLs;
 * external links forced to rel="noopener noreferrer" target="_blank".
 *
 * This stub exists only so types/imports resolve in the skeleton. It performs a
 * minimal text-escape (NOT the real sanitizer) and MUST be replaced in Task 2 with
 * the DOMPurify-backed implementation + the XSS red-team fixture test (§4.2).
 */

const ESCAPE_MAP: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

/** Placeholder: HTML-escape plain text. Replaced by markdown→sanitized-HTML in Task 2. */
export function sanitizeToHtml(input: string): string {
  return input.replace(/[&<>"']/g, (ch) => ESCAPE_MAP[ch] ?? ch);
}
