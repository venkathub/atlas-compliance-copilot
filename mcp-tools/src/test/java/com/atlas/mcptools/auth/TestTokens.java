package com.atlas.mcptools.auth;

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
 * Test helper that mints HS256, RFC 8707 audience-scoped clearance JWTs — the same shape the sim-IdP
 * will mint in task 5. Used to exercise the resource server (valid / expired / forged / wrong-aud) and
 * the per-call clearance re-check.
 */
public final class TestTokens {

    private TestTokens() {}

    /** Mint a fully custom token (HS256 over {@code SHA-256(signingKey)}). */
    public static String mint(String signingKey, String subject, String clearance, String issuer,
            String audience, Instant expiresAt) {
        try {
            JWTClaimsSet claims = new JWTClaimsSet.Builder()
                    .subject(subject)
                    .claim("clearance", clearance)
                    .issuer(issuer)
                    .audience(List.of(audience))
                    .issueTime(Date.from(Instant.now().minusSeconds(5)))
                    .expirationTime(Date.from(expiresAt))
                    .jwtID(UUID.randomUUID().toString())
                    .build();
            SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
            jwt.sign(new MACSigner(SecurityKeys.deriveHs256(signingKey)));
            return jwt.serialize();
        } catch (JOSEException e) {
            throw new IllegalStateException("failed to mint test token", e);
        }
    }

    /** A valid token for {@code subject} at {@code clearance}, expiring in 1 hour. */
    public static String valid(String signingKey, String issuer, String audience, String subject,
            String clearance) {
        return mint(signingKey, subject, clearance, issuer, audience, Instant.now().plusSeconds(3600));
    }
}
