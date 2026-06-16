package com.atlas.ragengine.api;

import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.DownstreamClearanceVerifier;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Optional;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * On the Gateway-fronted path, resolves the caller's clearance from the Gateway-asserted, independently
 * verified internal JWT (ADR-0034 / D-P3-5) and stashes it as a request attribute. When a valid
 * assertion is present, downstream resolution uses it and ignores the P1 {@code X-Atlas-Clearance}
 * shim header (the shim is retired on this path).
 *
 * <p>When no assertion is present (e.g. direct/test access, or P1 ITs), the filter is a no-op and the
 * existing {@code ClearanceResolver} path applies — keeping P1 behaviour intact.
 */
public class DownstreamClearanceFilter extends OncePerRequestFilter {

    /** Request attribute holding the verified {@link ClearanceLevel} when the Gateway asserted one. */
    public static final String ATTRIBUTE = "atlas.verifiedClearance";

    private final DownstreamClearanceVerifier verifier;

    public DownstreamClearanceFilter(DownstreamClearanceVerifier verifier) {
        this.verifier = verifier;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        Optional<ClearanceLevel> verified = verifier.verify(request.getHeader(DownstreamClearanceVerifier.HEADER));
        verified.ifPresent(level -> request.setAttribute(ATTRIBUTE, level));
        chain.doFilter(request, response);
    }
}
