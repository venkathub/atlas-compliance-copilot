package com.atlas.gateway.auth;

import static org.assertj.core.api.Assertions.assertThat;

import com.nimbusds.jose.crypto.MACVerifier;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.time.Instant;
import org.junit.jupiter.api.Test;

/**
 * Verifies the internal-hop signer (ADR-0034 / D-P3-5). The token must verify under the shared internal
 * secret using the {@code SHA-256(secret)} derivation — the exact derivation rag-engine's
 * {@code DownstreamClearanceVerifier} uses, which is what makes the cross-service hop trustworthy.
 */
class DownstreamClearanceSignerTest {

    private final GatewayProperties props =
            new GatewayProperties("http://localhost:8081", "shared-internal-secret");
    private final DownstreamClearanceSigner signer = new DownstreamClearanceSigner(props);

    @Test
    void signsAVerifiableShortLivedAssertion() throws Exception {
        String token = signer.sign("priya", Clearance.COMPLIANCE);

        SignedJWT jwt = SignedJWT.parse(token);
        boolean verified = jwt.verify(new MACVerifier(SecurityKeys.deriveHs256("shared-internal-secret")));
        assertThat(verified).isTrue();

        JWTClaimsSet claims = jwt.getJWTClaimsSet();
        assertThat(claims.getSubject()).isEqualTo("priya");
        assertThat(claims.getStringClaim("clearance")).isEqualTo("compliance");
        assertThat(claims.getIssuer()).isEqualTo(DownstreamClearanceSigner.ISSUER);
        assertThat(claims.getExpirationTime().toInstant()).isAfter(Instant.now());
        // Short-lived: expiry within ~2 minutes.
        assertThat(claims.getExpirationTime().toInstant()).isBefore(Instant.now().plusSeconds(120));
    }

    @Test
    void differentSecretDoesNotVerify() throws Exception {
        String token = signer.sign("priya", Clearance.COMPLIANCE);
        SignedJWT jwt = SignedJWT.parse(token);

        boolean verified = jwt.verify(new MACVerifier(SecurityKeys.deriveHs256("a-different-secret")));
        assertThat(verified).isFalse();
    }
}
