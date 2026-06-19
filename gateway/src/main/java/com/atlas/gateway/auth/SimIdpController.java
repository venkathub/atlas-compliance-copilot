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
 * Simulated identity / clearance provider (ADR-0034, realizes ADR-0003) — <b>dev/demo only</b>.
 *
 * <p>{@code POST /v1/auth/token} mints a cryptographically verifiable signed JWT clearance claim for a
 * known dev user. This stands in for a real federated IdP: it proves the verifiable-clearance
 * enforcement path the whole stack depends on, without a real OIDC provider (P3 non-goal). The token is
 * validated by {@link JwtClearanceFilter} on every subsequent request.
 */
@RestController
@RequestMapping("/v1/auth")
public class SimIdpController {

    private static final Logger log = LoggerFactory.getLogger(SimIdpController.class);

    private final ClearanceTokenService tokens;
    private final DevUserDirectory directory;

    public SimIdpController(ClearanceTokenService tokens, DevUserDirectory directory) {
        this.tokens = tokens;
        this.directory = directory;
    }

    /** Token request: a dev user id whose clearance the IdP looks up and asserts. */
    public record TokenRequest(String user) {
    }

    /** Token response (Bearer JWT + decoded metadata for convenience). */
    public record TokenResponse(String token, String tokenType, long expiresIn, String subject, String clearance) {
    }

    @PostMapping("/token")
    public ResponseEntity<TokenResponse> token(@RequestBody(required = false) TokenRequest request) {
        if (request == null || request.user() == null || request.user().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "user is required");
        }
        String user = request.user().strip();
        Clearance clearance = directory.clearanceFor(user)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "unknown user"));
        String token = tokens.mint(user, clearance);
        ClearanceTokenService.Claims claims = tokens.verify(token); // also yields exp for the response
        long expiresIn = Math.max(0, claims.expiresAt().getEpochSecond() - System.currentTimeMillis() / 1000);
        log.info("Minted clearance token for '{}' at '{}'", user, clearance.label());
        return ResponseEntity.ok(new TokenResponse(token, "Bearer", expiresIn, user, clearance.label()));
    }
}
