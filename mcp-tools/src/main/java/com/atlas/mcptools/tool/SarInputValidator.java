package com.atlas.mcptools.tool;

import java.util.List;
import java.util.regex.Pattern;

/**
 * Input-schema validation for {@code open_draft_sar} (P4_SPEC §2.3). Defense-in-depth over the MCP
 * JSON-schema: a bad {@code period}, an oversized {@code rationale}, or malformed {@code citations}
 * are rejected before any write. Throws {@link IllegalArgumentException} (surfaced as an MCP tool
 * error) with a precise message.
 */
public final class SarInputValidator {

    /** Reporting period, e.g. {@code 2026-Q2}. */
    public static final Pattern PERIOD_PATTERN = Pattern.compile("^[0-9]{4}-Q[1-4]$");

    /** Upper bound on the free-text rationale. */
    public static final int MAX_RATIONALE_LEN = 2000;

    private SarInputValidator() {}

    public static void validate(String account, String period, String rationale, List<Integer> citations) {
        requireText("account", account);
        requireText("period", period);
        if (!PERIOD_PATTERN.matcher(period).matches()) {
            throw new IllegalArgumentException("period must match ^[0-9]{4}-Q[1-4]$ (e.g. 2026-Q2)");
        }
        requireText("rationale", rationale);
        if (rationale.length() > MAX_RATIONALE_LEN) {
            throw new IllegalArgumentException(
                    "rationale exceeds " + MAX_RATIONALE_LEN + " characters");
        }
        if (citations == null || citations.isEmpty()) {
            throw new IllegalArgumentException("citations must be a non-empty array of integers");
        }
        if (citations.stream().anyMatch(c -> c == null)) {
            throw new IllegalArgumentException("citations must not contain null entries");
        }
    }

    private static void requireText(String field, String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
    }
}
