package com.atlas.gateway.auth;

import static org.assertj.core.api.Assertions.assertThat;

import com.nimbusds.jose.crypto.MACVerifier;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.time.Instant;
import org.junit.jupiter.api.Test;

/**
 * Unit tests for the RFC 8707 resource-scoped token issuer (ADR-0046). Verifies the minted token's
 * claims/signature and, crucially, that it satisfies the <b>same validation contract</b> the mcp-tools
 * OAuth 2.1 resource server enforces (signature over the shared HS256 key, {@code iss}, {@code aud},
 * {@code exp}) — proving the gateway→MCP hop will be accepted.
 */
class ResourceScopedTokenIssuerTest {

    private static final String SIGNING_KEY = "shared-mcp-signing-key";
    private static final IdpProperties IDP = new IdpProperties(SIGNING_KEY, "atlas-sim-idp", 3600, null);
    private static final ResourceTokenProperties RESOURCE =
            new ResourceTokenProperties("atlas-mcp-tools", 300);

    private final ResourceScopedTokenIssuer issuer = new ResourceScopedTokenIssuer(IDP, RESOURCE);

    @Test
    void mintsAudienceScopedShortLivedTokenWithJti() throws Exception {
        ResourceScopedTokenIssuer.ResourceToken minted = issuer.mint("priya", Clearance.COMPLIANCE);

        assertThat(minted.audience()).isEqualTo("atlas-mcp-tools");
        assertThat(minted.jwtId()).isNotBlank();
        assertThat(minted.expiresAt()).isBetween(Instant.now(), Instant.now().plusSeconds(301));

        JWTClaimsSet claims = SignedJWT.parse(minted.token()).getJWTClaimsSet();
        assertThat(claims.getSubject()).isEqualTo("priya");
        assertThat(claims.getStringClaim("clearance")).isEqualTo("compliance");
        assertThat(claims.getIssuer()).isEqualTo("atlas-sim-idp");
        assertThat(claims.getAudience()).containsExactly("atlas-mcp-tools");
        assertThat(claims.getJWTID()).isEqualTo(minted.jwtId());
    }

    @Test
    void eachTokenHasAUniqueJti() {
        String a = issuer.mint("priya", Clearance.COMPLIANCE).jwtId();
        String b = issuer.mint("priya", Clearance.COMPLIANCE).jwtId();
        assertThat(a).isNotEqualTo(b);
    }

    @Test
    void mintedTokenSatisfiesTheResourceServerContract() {
        String token = issuer.mint("priya", Clearance.COMPLIANCE).token();
        // Exactly what mcp-tools' ResourceServerConfig validates: HS256 over SHA-256(shared key),
        // issuer, audience (RFC 8707), expiry, and the presence of subject + clearance.
        assertThat(satisfiesResourceServerContract(token, SIGNING_KEY, "atlas-sim-idp", "atlas-mcp-tools"))
                .isTrue();
    }

    @Test
    void wrongAudienceFailsTheResourceServerContract() {
        ResourceScopedTokenIssuer other = new ResourceScopedTokenIssuer(
                IDP, new ResourceTokenProperties("some-other-resource", 300));
        String token = other.mint("priya", Clearance.COMPLIANCE).token();
        assertThat(satisfiesResourceServerContract(token, SIGNING_KEY, "atlas-sim-idp", "atlas-mcp-tools"))
                .isFalse();
    }

    /** Mirror of the mcp-tools resource-server validation, using Nimbus (no Spring Security on the gateway). */
    private static boolean satisfiesResourceServerContract(String token, String signingKey,
            String expectedIssuer, String expectedAudience) {
        try {
            SignedJWT jwt = SignedJWT.parse(token);
            if (!jwt.verify(new MACVerifier(SecurityKeys.deriveHs256(signingKey)))) {
                return false;
            }
            JWTClaimsSet c = jwt.getJWTClaimsSet();
            boolean issOk = expectedIssuer.equals(c.getIssuer());
            boolean audOk = c.getAudience() != null && c.getAudience().contains(expectedAudience);
            boolean expOk = c.getExpirationTime() != null
                    && c.getExpirationTime().toInstant().isAfter(Instant.now());
            boolean subjectOk = c.getSubject() != null && c.getStringClaim("clearance") != null;
            return issOk && audOk && expOk && subjectOk;
        } catch (Exception e) {
            return false;
        }
    }
}
