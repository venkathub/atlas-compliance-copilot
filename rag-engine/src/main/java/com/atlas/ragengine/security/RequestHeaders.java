package com.atlas.ragengine.security;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;

/**
 * Servlet-free, case-insensitive view of request headers, so {@link ClearanceResolver} is unit
 * testable without a {@code HttpServletRequest}. A thin adapter from the real request is added with
 * the controller (P1 task 7).
 */
public final class RequestHeaders {

    private final Map<String, String> values;

    private RequestHeaders(Map<String, String> normalized) {
        this.values = normalized;
    }

    public static RequestHeaders of(Map<String, String> headers) {
        Map<String, String> normalized = new HashMap<>();
        if (headers != null) {
            headers.forEach((k, v) -> {
                if (k != null && v != null) {
                    normalized.put(k.toLowerCase(Locale.ROOT), v);
                }
            });
        }
        return new RequestHeaders(normalized);
    }

    public Optional<String> get(String name) {
        if (name == null) {
            return Optional.empty();
        }
        String v = values.get(name.toLowerCase(Locale.ROOT));
        return (v == null || v.isBlank()) ? Optional.empty() : Optional.of(v.strip());
    }
}
