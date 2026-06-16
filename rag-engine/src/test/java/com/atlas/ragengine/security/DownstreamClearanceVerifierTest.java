package com.atlas.ragengine.security;

import static org.assertj.core.api.Assertions.assertThat;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.Date;
import java.util.Optional;
import org.junit.jupiter.api.Test;

/**
 * Verifies that rag-engine independently validates the Gateway-asserted internal clearance JWT
 * (ADR-0034 / D-P3-5). The helper here MIRRORS the Gateway's {@code DownstreamClearanceSigner}
 * (HS256 over {@code SHA-256(secret)}, issuer {@code atlas-gateway}); a green test proves the two
 * services agree on the wire contract.
 */
class DownstreamClearanceVerifierTest {

    private static final String SECRET = "shared-internal-secret";

    private final DownstreamClearanceVerifier verifier =
            new DownstreamClearanceVerifier(new InternalClearanceProperties(SECRET));

    @Test
    void acceptsValidGatewayAssertion() {
        String token = sign(SECRET, "atlas-gateway", "priya", "compliance", Instant.now().plusSeconds(60));
        Optional<ClearanceLevel> result = verifier.verify(token);
        assertThat(result).contains(ClearanceLevel.COMPLIANCE);
    }

    @Test
    void rejectsWrongSecret() {
        String token = sign("attacker-secret", "atlas-gateway", "priya", "restricted", Instant.now().plusSeconds(60));
        assertThat(verifier.verify(token)).isEmpty();
    }

    @Test
    void rejectsExpiredAssertion() {
        String token = sign(SECRET, "atlas-gateway", "priya", "compliance", Instant.now().minusSeconds(5));
        assertThat(verifier.verify(token)).isEmpty();
    }

    @Test
    void rejectsWrongIssuer() {
        String token = sign(SECRET, "not-the-gateway", "priya", "compliance", Instant.now().plusSeconds(60));
        assertThat(verifier.verify(token)).isEmpty();
    }

    @Test
    void rejectsAbsentOrBlank() {
        assertThat(verifier.verify(null)).isEmpty();
        assertThat(verifier.verify("   ")).isEmpty();
        assertThat(verifier.verify("not-a-jwt")).isEmpty();
    }

    /** Mirrors the Gateway signer: HS256 over SHA-256(secret). */
    private static String sign(String secret, String issuer, String sub, String clearance, Instant exp) {
        try {
            byte[] key = MessageDigest.getInstance("SHA-256").digest(secret.getBytes(StandardCharsets.UTF_8));
            JWTClaimsSet claims = new JWTClaimsSet.Builder()
                    .subject(sub)
                    .claim("clearance", clearance)
                    .issuer(issuer)
                    .issueTime(Date.from(Instant.now().minusSeconds(1)))
                    .expirationTime(Date.from(exp))
                    .build();
            SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
            jwt.sign(new MACSigner(key));
            return jwt.serialize();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
