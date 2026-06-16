package com.atlas.gateway.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.time.Instant;
import java.util.Date;
import org.junit.jupiter.api.Test;

class ClearanceTokenServiceTest {

    private final IdpProperties props =
            new IdpProperties("test-signing-key", "atlas-sim-idp", 3600, null);
    private final ClearanceTokenService service = new ClearanceTokenService(props);

    @Test
    void mintThenVerifyRoundTrips() {
        String token = service.mint("priya", Clearance.COMPLIANCE);
        ClearanceTokenService.Claims claims = service.verify(token);

        assertThat(claims.subject()).isEqualTo("priya");
        assertThat(claims.clearance()).isEqualTo(Clearance.COMPLIANCE);
        assertThat(claims.jwtId()).isNotBlank();
        assertThat(claims.expiresAt()).isAfter(Instant.now());
    }

    @Test
    void rejectsMalformedToken() {
        assertThatThrownBy(() -> service.verify("not-a-jwt"))
                .isInstanceOf(ClearanceTokenService.InvalidTokenException.class);
    }

    @Test
    void rejectsForgedSignature() {
        // Minted with a DIFFERENT signing key → signature must not verify under our service's key.
        ClearanceTokenService other =
                new ClearanceTokenService(new IdpProperties("attacker-key", "atlas-sim-idp", 3600, null));
        String forged = other.mint("priya", Clearance.RESTRICTED);

        assertThatThrownBy(() -> service.verify(forged))
                .isInstanceOf(ClearanceTokenService.InvalidTokenException.class);
    }

    @Test
    void rejectsWrongIssuer() {
        ClearanceTokenService wrongIssuer =
                new ClearanceTokenService(new IdpProperties("test-signing-key", "evil-idp", 3600, null));
        String token = wrongIssuer.mint("priya", Clearance.COMPLIANCE);

        assertThatThrownBy(() -> service.verify(token))
                .isInstanceOf(ClearanceTokenService.InvalidTokenException.class);
    }

    @Test
    void rejectsExpiredToken() throws Exception {
        // Hand-build a correctly-signed but already-expired token.
        byte[] key = SecurityKeys.deriveHs256("test-signing-key");
        Instant past = Instant.now().minusSeconds(120);
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .subject("priya")
                .claim("clearance", "compliance")
                .issuer("atlas-sim-idp")
                .issueTime(Date.from(past.minusSeconds(60)))
                .expirationTime(Date.from(past))
                .build();
        SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
        jwt.sign(new MACSigner(key));

        assertThatThrownBy(() -> service.verify(jwt.serialize()))
                .isInstanceOf(ClearanceTokenService.InvalidTokenException.class)
                .hasMessageContaining("expired");
    }
}
