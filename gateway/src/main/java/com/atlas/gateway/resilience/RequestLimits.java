package com.atlas.gateway.resilience;

import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

/**
 * Per-request resource limits (ADR-0038, LLM10): a deterministic input-size cap and the max-output-token
 * value forwarded to rag-engine. Rejecting oversized input early (before embedding/routing/model work)
 * closes a cheap DoS / cost-drain vector.
 */
public class RequestLimits {

    private final int maxInputTokens;
    private final int maxOutputTokens;

    public RequestLimits(int maxInputTokens, int maxOutputTokens) {
        this.maxInputTokens = maxInputTokens;
        this.maxOutputTokens = maxOutputTokens;
    }

    /** Reject an over-large query with {@code 413} before any model/embedding work. */
    public void validateInputSize(String query) {
        if (estimateTokens(query) > maxInputTokens) {
            throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE,
                    "query exceeds the maximum input size (" + maxInputTokens + " tokens)");
        }
    }

    public int maxOutputTokens() {
        return maxOutputTokens;
    }

    /** Deterministic, model-free token estimate (~4 chars/token) — stable for CI. */
    public static int estimateTokens(String text) {
        if (text == null || text.isBlank()) {
            return 0;
        }
        return (int) Math.ceil(text.strip().length() / 4.0);
    }
}
