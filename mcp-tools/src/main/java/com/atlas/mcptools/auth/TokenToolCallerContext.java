package com.atlas.mcptools.auth;

import com.atlas.mcptools.tool.ToolCallerContext;
import org.springframework.context.annotation.Primary;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;

/**
 * Token-backed {@link ToolCallerContext} (ADR-0046): derives the caller + clearance from the validated
 * (RFC 8707 audience-restricted) Bearer JWT that the resource-server filter placed in the security
 * context. Registered as {@code @Primary}, it supersedes the task-3 default for injection.
 *
 * <p>The WebMVC Streamable-HTTP MCP server executes the tool on the request thread, so the
 * {@code SecurityContextHolder} thread-local carries the {@link JwtAuthenticationToken} inside the tool.
 */
@Component
@Primary
public class TokenToolCallerContext implements ToolCallerContext {

    @Override
    public CallerIdentity current() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (!(auth instanceof JwtAuthenticationToken jwtAuth)) {
            throw new IllegalStateException("no authenticated JWT in the security context");
        }
        Jwt jwt = jwtAuth.getToken();
        String caller = jwt.getSubject();
        String clearance = jwt.getClaimAsString("clearance");
        if (caller == null || clearance == null) {
            throw new IllegalStateException("token is missing subject/clearance");
        }
        return new CallerIdentity(caller, clearance);
    }
}
