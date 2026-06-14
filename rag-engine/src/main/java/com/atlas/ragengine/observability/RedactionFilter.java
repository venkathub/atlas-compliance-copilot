package com.atlas.ragengine.observability;

import java.util.List;
import java.util.regex.Pattern;

/**
 * Redacts PII before any prompt/response/context text is attached to a trace (ADR-0030 / D-P2-10).
 *
 * <p>Only ever invoked when content capture is explicitly turned on ({@code ATLAS_TRACE_CONTENT=full},
 * dev-only). It strips structured PII (SSN-, passport-, account-style tokens) plus a configurable
 * exact-match deny-list (the P2 red-team fixtures seed this with the known planted PII strings). The
 * compliance guarantee in prod is the OFF default; this filter is the second line for dev traces.
 */
public class RedactionFilter {

    public static final String MASK = "[REDACTED]";

    // Structured PII heuristics. Order matters (longer/more specific first).
    private static final List<Pattern> PII_PATTERNS = List.of(
            Pattern.compile("\\b\\d{3}-\\d{2}-\\d{4}\\b"),          // US SSN  900-12-3456
            Pattern.compile("\\b[A-Z]\\d{6,9}\\b"),                  // passport  X1234567
            Pattern.compile("\\b\\d{10,}\\b"),                       // long account/card numbers
            Pattern.compile("[\\w.+-]+@[\\w-]+\\.[\\w.-]+"));        // email addresses

    private final List<String> denylist;

    public RedactionFilter(List<String> denylist) {
        this.denylist = denylist == null ? List.of() : List.copyOf(denylist);
    }

    public static RedactionFilter defaults() {
        return new RedactionFilter(List.of());
    }

    /** Return {@code text} with PII patterns and deny-listed strings masked. Null-safe. */
    public String redact(String text) {
        if (text == null || text.isEmpty()) {
            return text;
        }
        String out = text;
        for (String literal : denylist) {
            if (literal != null && !literal.isBlank()) {
                out = out.replace(literal, MASK);
            }
        }
        for (Pattern p : PII_PATTERNS) {
            out = p.matcher(out).replaceAll(MASK);
        }
        return out;
    }
}
