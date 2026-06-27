import { describe, it, expect } from "vitest";
import { sanitizeMarkdown, sanitizeText } from "../src/lib/sanitize.ts";

/**
 * LLM05 "Improper Output Handling" — the PHASE-BLOCKING render-boundary gate (§4.2).
 * Untrusted model output carrying XSS payloads must render INERT: no executable
 * script, no event handlers, no javascript:/data: URIs.
 */
describe("sanitizeMarkdown — LLM05 XSS gate", () => {
  it("strips <script> tags entirely", () => {
    const html = sanitizeMarkdown("Hello <script>alert('xss')</script> world");
    expect(html).not.toContain("<script");
    expect(html.toLowerCase()).not.toContain("alert(");
  });

  it("strips inline event handlers (onerror/onclick)", () => {
    const html = sanitizeMarkdown('<img src="x" onerror="alert(1)"> <a onclick="evil()">x</a>');
    expect(html.toLowerCase()).not.toContain("onerror");
    expect(html.toLowerCase()).not.toContain("onclick");
  });

  it("strips javascript: URLs from markdown links", () => {
    const html = sanitizeMarkdown("[click me](javascript:alert(1))");
    expect(html.toLowerCase()).not.toContain("javascript:");
  });

  it("strips data: URIs (HTML smuggling vector)", () => {
    const html = sanitizeMarkdown('<a href="data:text/html;base64,PHNjcmlwdD4=">x</a>');
    expect(html.toLowerCase()).not.toContain("data:text/html");
  });

  it("removes <iframe>/<object> embeds", () => {
    const html = sanitizeMarkdown('<iframe src="https://evil.test"></iframe>');
    expect(html.toLowerCase()).not.toContain("<iframe");
  });

  it("renders legitimate markdown (bold, list, code)", () => {
    const html = sanitizeMarkdown("**bold** and `code`\n\n- one\n- two");
    expect(html).toContain("<strong>bold</strong>");
    expect(html).toContain("<code>code</code>");
    expect(html).toContain("<li>one</li>");
  });

  it("hardens external links with target+rel", () => {
    const html = sanitizeMarkdown("[Atlas](https://example.test/doc)");
    expect(html).toContain('href="https://example.test/doc"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
  });
});

describe("sanitizeText — plain-text snippets", () => {
  it("strips all markup to inert text", () => {
    const out = sanitizeText("<script>alert(1)</script><b>hi</b>");
    expect(out).not.toContain("<script");
    expect(out).not.toContain("<b>");
  });

  it("handles null/undefined safely", () => {
    expect(sanitizeText(null)).toBe("");
    expect(sanitizeText(undefined)).toBe("");
  });
});
