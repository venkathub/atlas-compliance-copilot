package com.atlas.gateway.auth;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.JWSSigner;
import com.nimbusds.jose.JWSVerifier;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jose.crypto.MACVerifier;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.text.ParseException;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;

/**
 * Mints and verifies the simulated-IdP client clearance JWT (ADR-0034, realizes ADR-0003).
 *
 * <p>HS256 signed with {@code SHA-256(ATLAS_IDP_SIGNING_KEY)} (see {@link SecurityKeys}). The token is
 * the cryptographically verifiable clearance claim the Gateway validates on every request — the single
 * trust boundary. Claims: {@code sub, clearance, iss, iat, exp, jti} (P3_SPEC §2.3).
 */
public class ClearanceTokenService {

    private final byte[] key;
    private final String issuer;
    private final long ttlSeconds;

    public ClearanceTokenService(IdpProperties props) {
        this.key = SecurityKeys.deriveHs256(props.signingKey());
        this.issuer = props.issuer();
        this.ttlSeconds = props.tokenTtlSeconds();
    }

    /** A verified, validated token payload. */
    public record Claims(String subject, Clearance clearance, String jwtId, Instant expiresAt) {
    }

    /** Mint a signed clearance JWT for {@code subject} at {@code clearance}. */
    public String mint(String subject, Clearance clearance) {
        Instant now = Instant.now();
        Instant exp = now.plusSeconds(ttlSeconds);
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .subject(subject)
                .claim("clearance", clearance.label())
                .issuer(issuer)
                .issueTime(Date.from(now))
                .expirationTime(Date.from(exp))
                .jwtID(UUID.randomUUID().toString())
                .build();
        try {
            SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
            JWSSigner signer = new MACSigner(key);
            jwt.sign(signer);
            return jwt.serialize();
        } catch (JOSEException e) {
            throw new IllegalStateException("Failed to mint clearance JWT", e);
        }
    }

    /**
     * Verify a serialized clearance JWT: signature, {@code exp}, {@code iss}, and a parseable
     * {@code clearance} claim.
     *
     * @throws InvalidTokenException if the token is malformed, tampered, expired, wrong-issuer, or
     *                               carries an unknown clearance
     */
    public Claims verify(String token) {
        SignedJWT jwt;
        try {
            jwt = SignedJWT.parse(token);
        } catch (ParseException e) {
            throw new InvalidTokenException("malformed token");
        }
        try {
            JWSVerifier verifier = new MACVerifier(key);
            if (!jwt.verify(verifier)) {
                throw new InvalidTokenException("bad signature");
            }
            JWTClaimsSet claims = jwt.getJWTClaimsSet();
            Date exp = claims.getExpirationTime();
            if (exp == null || exp.toInstant().isBefore(Instant.now())) {
                throw new InvalidTokenException("expired");
            }
            if (!issuer.equals(claims.getIssuer())) {
                throw new InvalidTokenException("wrong issuer");
            }
            String clearance = claims.getStringClaim("clearance");
            String subject = claims.getSubject();
            if (clearance == null || subject == null) {
                throw new InvalidTokenException("missing subject/clearance");
            }
            return new Claims(subject, Clearance.fromLabel(clearance), claims.getJWTID(), exp.toInstant());
        } catch (JOSEException | ParseException | IllegalArgumentException e) {
            throw new InvalidTokenException("invalid token: " + e.getMessage());
        }
    }

    /** Thrown for any invalid/expired/forged token — mapped to {@code 401} by the filter. */
    public static class InvalidTokenException extends RuntimeException {
        public InvalidTokenException(String message) {
            super(message);
        }
    }
}
