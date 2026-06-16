package com.atlas.gateway.auth;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * The trust boundary (ADR-0034). Validates the {@code Authorization: Bearer <jwt>} clearance claim on
 * every protected request and resolves the caller's clearance, which the query path re-asserts to
 * {@code rag-engine}. A missing/expired/forged token → {@code 401}. The P1 {@code X-Atlas-Clearance}
 * header shim is never consulted here — clearance comes only from the verified token.
 *
 * <p>Unprotected paths: {@code /v1/auth/**} (mint a token) and {@code /actuator/**} (health/metrics).
 */
public class JwtClearanceFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(JwtClearanceFilter.class);
    private static final String BEARER_PREFIX = "Bearer ";

    private final ClearanceTokenService tokens;

    public JwtClearanceFilter(ClearanceTokenService tokens) {
        this.tokens = tokens;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return path.startsWith("/v1/auth/") || path.startsWith("/actuator/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (header == null || !header.startsWith(BEARER_PREFIX)) {
            unauthorized(response, "missing bearer token");
            return;
        }
        String token = header.substring(BEARER_PREFIX.length()).strip();
        try {
            ClearanceTokenService.Claims claims = tokens.verify(token);
            request.setAttribute(CallerClearance.ATTRIBUTE,
                    new CallerClearance(claims.subject(), claims.clearance()));
        } catch (ClearanceTokenService.InvalidTokenException e) {
            log.debug("Rejected token: {}", e.getMessage());
            unauthorized(response, "invalid token");
            return;
        }
        chain.doFilter(request, response);
    }

    private void unauthorized(HttpServletResponse response, String reason) throws IOException {
        response.setStatus(HttpStatus.UNAUTHORIZED.value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write("{\"error\":\"unauthorized\",\"reason\":\"" + reason + "\"}");
    }
}
