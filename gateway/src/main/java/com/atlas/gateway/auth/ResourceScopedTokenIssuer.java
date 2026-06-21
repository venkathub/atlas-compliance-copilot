package com.atlas.gateway.auth;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.UUID;

/**
 * Mints <b>resource-scoped, audience-restricted</b> (RFC 8707) clearance JWTs for the MCP tool hop
 * (ADR-0046, extends ADR-0003/0034). Same HS256 signing key + issuer as the client clearance token
 * ({@link ClearanceTokenService}), plus an {@code aud} naming the MCP resource server, a short {@code exp},
 * and a unique {@code jti}.
 *
 * <p>The unique {@code jti} + short {@code exp} are the groundwork for single-use, replay-protected
 * approval (ASI07): the agent binds the approval to the {@code run_id} + checkpoint and a consumed
 * {@code jti} cannot be replayed (the binding + consumption land with the agent, P4 task 8).
 */
public class ResourceScopedTokenIssuer {

    private final byte[] key;
    private final String issuer;
    private final String audience;
    private final long ttlSeconds;

    public ResourceScopedTokenIssuer(IdpProperties idp, ResourceTokenProperties resource) {
        this.key = SecurityKeys.deriveHs256(idp.signingKey());
        this.issuer = idp.issuer();
        this.audience = resource.audience();
        this.ttlSeconds = resource.ttlSeconds();
    }

    /** A minted resource-scoped token + decoded metadata. */
    public record ResourceToken(String token, String audience, String jwtId, Instant expiresAt) {
    }

    /** Mint an aud-scoped, short-lived clearance token for the MCP hop. */
    public ResourceToken mint(String subject, Clearance clearance) {
        Instant now = Instant.now();
        Instant exp = now.plusSeconds(ttlSeconds);
        String jti = UUID.randomUUID().toString();
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .subject(subject)
                .claim("clearance", clearance.label())
                .issuer(issuer)
                .audience(List.of(audience))
                .issueTime(Date.from(now))
                .expirationTime(Date.from(exp))
                .jwtID(jti)
                .build();
        try {
            SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
            jwt.sign(new MACSigner(key));
            return new ResourceToken(jwt.serialize(), audience, jti, exp);
        } catch (JOSEException e) {
            throw new IllegalStateException("Failed to mint resource-scoped token", e);
        }
    }
}
