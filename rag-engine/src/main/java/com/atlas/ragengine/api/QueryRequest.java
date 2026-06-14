package com.atlas.ragengine.api;

/**
 * {@code POST /v1/query} request body. {@code topK} is optional (defaults applied downstream).
 *
 * <p>{@code includeContexts} (default false) is the eval-context opt-in (ADR-0023 / D-P2-3): when true
 * the response carries the full RBAC-filtered context chunks the model saw, which the RAGAS harness needs
 * (citation snippets are truncated). Normal callers/UI leave it unset and are unaffected.
 */
public record QueryRequest(String query, Integer topK, Boolean includeContexts) {

    public int topKOrDefault() {
        return topK == null ? 0 : topK; // 0 => service uses configured default
    }

    public boolean includeContextsOrDefault() {
        return includeContexts != null && includeContexts;
    }
}
