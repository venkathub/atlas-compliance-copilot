package com.atlas.gateway.auth;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/**
 * Mints resource-scoped (RFC 8707) tokens for the MCP tool hop (ADR-0046, P4 task 5) — <b>dev/demo
 * only</b>, additive to the simulated IdP. {@code POST /v1/auth/resource-token} looks up the dev user's
 * clearance and issues an aud-restricted, short-lived clearance JWT the agent forwards to the MCP server
 * (which validates it as an OAuth 2.1 resource server). Lives under {@code /v1/auth/**}, which the
 * {@link JwtClearanceFilter} skips.
 */
@RestController
@RequestMapping("/v1/auth")
public class ResourceTokenController {

    private static final Logger log = LoggerFactory.getLogger(ResourceTokenController.class);

    private final ResourceScopedTokenIssuer issuer;
    private final DevUserDirectory directory;

    public ResourceTokenController(ResourceScopedTokenIssuer issuer, DevUserDirectory directory) {
        this.issuer = issuer;
        this.directory = directory;
    }

    /** Request: the dev user whose clearance the IdP asserts into the resource-scoped token. */
    public record ResourceTokenRequest(String user) {
    }

    /** Response: the aud-scoped Bearer JWT + decoded metadata. */
    public record ResourceTokenResponse(
            String token, String tokenType, long expiresIn, String subject, String clearance,
            String audience) {
    }

    @PostMapping("/resource-token")
    public ResponseEntity<ResourceTokenResponse> resourceToken(
            @RequestBody(required = false) ResourceTokenRequest request) {
        if (request == null || request.user() == null || request.user().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "user is required");
        }
        String user = request.user().strip();
        Clearance clearance = directory.clearanceFor(user)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "unknown user"));
        ResourceScopedTokenIssuer.ResourceToken minted = issuer.mint(user, clearance);
        long expiresIn = Math.max(0, minted.expiresAt().getEpochSecond() - System.currentTimeMillis() / 1000);
        log.info("Minted resource-scoped token for '{}' at '{}' (aud={})",
                user, clearance.label(), minted.audience());
        return ResponseEntity.ok(new ResourceTokenResponse(
                minted.token(), "Bearer", expiresIn, user, clearance.label(), minted.audience()));
    }
}
