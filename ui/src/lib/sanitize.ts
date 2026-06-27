import DOMPurify from "dompurify";
import { marked } from "marked";

/**
 * sanitize — the LLM05 render-boundary defense ("Improper Output Handling").
 *
 * Model/markdown output (answers, citations, rationales, audit rows) is UNTRUSTED
 * interpreter input — "the new XSS" (OWASP/Auth0, 2026). Everything rendered as HTML
 * passes through this allowlist FIRST. This is the client-side first wall; the Caddy
 * proxy CSP (Task 7) is the independent second wall (defense-in-depth, ADR-0058).
 *
 * Guarantees enforced here:
 *  - no <script>, no inline event handlers (onclick/onerror/…), no <style>/<iframe>/
 *    <object>/<embed>/<form>/<input>;
 *  - URLs restricted to http(s)/mailto/tel/relative/anchor — `javascript:` and
 *    `data:` URIs are stripped;
 *  - every external link is forced to target="_blank" rel="noopener noreferrer".
 */

// GFM markdown, no raw-HTML niceties that would widen the surface. marked escapes
// most HTML already; DOMPurify is the authoritative gate regardless.
marked.setOptions({ gfm: true, breaks: false });

// Allowlisted URI schemes (case-insensitive): http(s), mailto, tel, relative, anchor.
const ALLOWED_URI_REGEXP = /^(?:https?:|mailto:|tel:|\/|\.|#)/i;

let hooksRegistered = false;
function ensureHooks(): void {
  if (hooksRegistered) return;
  // Force safe link semantics on every anchor that survives sanitization.
  DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (node.nodeName === "A") {
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer");
    }
  });
  hooksRegistered = true;
}

/** Render untrusted markdown to SAFE, sanitized HTML (for dangerouslySetInnerHTML). */
export function sanitizeMarkdown(markdown: string | null | undefined): string {
  ensureHooks();
  const rawHtml = marked.parse(markdown ?? "", { async: false });
  return DOMPurify.sanitize(rawHtml, {
    ALLOWED_URI_REGEXP,
    FORBID_TAGS: ["style", "form", "input", "iframe", "object", "embed"],
    FORBID_ATTR: ["style"],
    ADD_ATTR: ["target", "rel"],
  });
}

/**
 * Strip ALL markup from untrusted text (citation snippets, audit cells). Returns
 * plain text safe to drop into the DOM. React already escapes text nodes; this is
 * belt-and-suspenders so the value is inert even if ever rendered as HTML.
 */
export function sanitizeText(text: string | null | undefined): string {
  return DOMPurify.sanitize(text ?? "", { ALLOWED_TAGS: [], ALLOWED_ATTR: [] });
}
