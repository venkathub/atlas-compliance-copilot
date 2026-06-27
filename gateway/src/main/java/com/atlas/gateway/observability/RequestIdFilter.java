package com.atlas.gateway.observability;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.UUID;
import java.util.regex.Pattern;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Establishes a correlation id for every request so logs and traces can be stitched across the
 * gateway → rag-engine → (agents → mcp-tools) hops (P6 Task 3).
 *
 * <p>The id is taken from an inbound {@code X-Request-Id} when present and well-formed, otherwise a
 * fresh UUID is minted. It is published to SLF4J {@link MDC} (so the structured JSON encoder emits it
 * on every line) and echoed on the response header. The inbound value is validated against a strict
 * allow-list before use — a client header is untrusted input and must not be able to inject newlines
 * or control characters into log lines (OWASP log-injection).
 *
 * <p>Runs at {@link Ordered#HIGHEST_PRECEDENCE} so even auth rejections (401/403) carry a request id.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class RequestIdFilter extends OncePerRequestFilter {

    public static final String HEADER = "X-Request-Id";
    public static final String MDC_KEY = "requestId";

    /** Conservative allow-list: ids are short, printable, no control chars (anti log-injection). */
    private static final Pattern SAFE_ID = Pattern.compile("[A-Za-z0-9._-]{1,64}");

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
            FilterChain chain) throws ServletException, IOException {
        String requestId = resolve(request.getHeader(HEADER));
        MDC.put(MDC_KEY, requestId);
        response.setHeader(HEADER, requestId);
        try {
            chain.doFilter(request, response);
        } finally {
            MDC.remove(MDC_KEY);
        }
    }

    private static String resolve(String inbound) {
        if (inbound != null && SAFE_ID.matcher(inbound).matches()) {
            return inbound;
        }
        return UUID.randomUUID().toString();
    }
}
