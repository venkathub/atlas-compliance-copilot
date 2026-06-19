package com.atlas.gateway.safety;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Deterministic finance-PII redactor on the hot path (ADR-0037, OWASP LLM02). Detects a known, bounded
 * set of finance-PII — account numbers, SSN/TIN, passport numbers, dates of birth — plus a configurable
 * literal denylist of restricted entities/names, and masks each with a {@code [REDACTED:TYPE]} marker.
 *
 * <p>Fast, cassette-friendly, and CI-deterministic; the off-path Presidio deep-scan (deferred) adds NER
 * breadth for free-text/unknown names, distilling new findings back into these rules. Redaction events are
 * surfaced as <b>counts/types only — never the PII itself</b> (consistent with ADR-0030 / D-P2-10).
 */
public class PiiRedactor {

    /** Ordered so multi-token denylist terms are masked before single-token structured patterns. */
    private final List<String> nameDenylist;

    // Structured finance-PII. \b anchors avoid over-matching; order is most-specific-first.
    private static final Pattern SSN_TIN = Pattern.compile("\\b\\d{3}-\\d{2}-\\d{4}\\b");
    private static final Pattern DOB = Pattern.compile(
            "\\b(?:\\d{4}-\\d{2}-\\d{2}|\\d{1,2}/\\d{1,2}/\\d{4})\\b");
    private static final Pattern PASSPORT = Pattern.compile("\\b[A-Z]\\d{7}\\b");
    private static final Pattern ACCOUNT = Pattern.compile("\\b\\d{8,}\\b");

    public PiiRedactor(List<String> nameDenylist) {
        this.nameDenylist = nameDenylist == null ? List.of() : nameDenylist;
    }

    /** The result of a redaction pass: the masked text + per-type match counts (no PII). */
    public record Redaction(String text, Map<String, Integer> counts) {
        public boolean applied() {
            return !counts.isEmpty();
        }
    }

    public Redaction redact(String input) {
        if (input == null || input.isEmpty()) {
            return new Redaction(input, Map.of());
        }
        Map<String, Integer> counts = new LinkedHashMap<>();
        String text = input;
        // 1) Literal denylist (names / restricted entity phrases), case-insensitive.
        for (String term : nameDenylist) {
            if (term == null || term.isBlank()) {
                continue;
            }
            Pattern p = Pattern.compile(Pattern.quote(term), Pattern.CASE_INSENSITIVE);
            text = apply(text, p, "DENYLIST_TERM", counts);
        }
        // 2) Structured finance-PII (specific → general so SSN/DOB aren't swallowed by ACCOUNT).
        text = apply(text, SSN_TIN, "SSN_TIN", counts);
        text = apply(text, DOB, "DOB", counts);
        text = apply(text, PASSPORT, "PASSPORT", counts);
        text = apply(text, ACCOUNT, "ACCOUNT_NUMBER", counts);
        return new Redaction(text, counts);
    }

    private static String apply(String text, Pattern pattern, String type, Map<String, Integer> counts) {
        Matcher m = pattern.matcher(text);
        StringBuilder sb = new StringBuilder();
        int hits = 0;
        while (m.find()) {
            hits++;
            m.appendReplacement(sb, Matcher.quoteReplacement("[REDACTED:" + type + "]"));
        }
        m.appendTail(sb);
        if (hits > 0) {
            counts.merge(type, hits, Integer::sum);
        }
        return sb.toString();
    }
}
