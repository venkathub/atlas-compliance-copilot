package com.atlas.gateway.safety;

import java.util.regex.Pattern;

/**
 * Output handling / sanitization at egress (ADR-0037, OWASP LLM05 Improper Output Handling). Strips
 * executable/active markup from model output and neutralizes residual HTML so no script or markup
 * injection reaches a downstream consumer (browser/UI).
 *
 * <p>Deterministic and conservative: remove {@code <script>}/{@code <style>}/{@code <iframe>} blocks and
 * {@code javascript:} URIs outright, then HTML-escape any remaining angle brackets so leftover tags render
 * as inert text rather than markup.
 */
public class OutputSanitizer {

    private static final Pattern SCRIPTISH = Pattern.compile(
            "<\\s*(script|style|iframe|object|embed)\\b[\\s\\S]*?<\\s*/\\s*\\1\\s*>",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern DANGLING_SCRIPT_OPEN = Pattern.compile(
            "<\\s*(script|style|iframe|object|embed)\\b[^>]*>", Pattern.CASE_INSENSITIVE);
    private static final Pattern JS_URI = Pattern.compile("javascript:", Pattern.CASE_INSENSITIVE);
    private static final Pattern EVENT_HANDLER = Pattern.compile("\\son\\w+\\s*=", Pattern.CASE_INSENSITIVE);

    /** The result of a sanitization pass: the cleaned text + the number of unsafe constructs removed. */
    public record Sanitized(String text, int removed) {
        public boolean applied() {
            return removed > 0;
        }
    }

    public Sanitized sanitize(String input) {
        if (input == null || input.isEmpty()) {
            return new Sanitized(input, 0);
        }
        int removed = 0;
        String text = input;

        removed += count(text, SCRIPTISH);
        text = SCRIPTISH.matcher(text).replaceAll("");
        removed += count(text, DANGLING_SCRIPT_OPEN);
        text = DANGLING_SCRIPT_OPEN.matcher(text).replaceAll("");
        removed += count(text, JS_URI);
        text = JS_URI.matcher(text).replaceAll("blocked:");
        removed += count(text, EVENT_HANDLER);
        text = EVENT_HANDLER.matcher(text).replaceAll(" data-blocked=");

        // Neutralize any residual markup so it renders as inert text, not HTML.
        if (text.indexOf('<') >= 0 || text.indexOf('>') >= 0) {
            String escaped = text.replace("<", "&lt;").replace(">", "&gt;");
            if (!escaped.equals(text)) {
                removed++;
                text = escaped;
            }
        }
        return new Sanitized(text, removed);
    }

    private static int count(String text, Pattern p) {
        var m = p.matcher(text);
        int n = 0;
        while (m.find()) {
            n++;
        }
        return n;
    }
}
