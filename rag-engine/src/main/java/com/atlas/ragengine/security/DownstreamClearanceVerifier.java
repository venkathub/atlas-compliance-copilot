package com.atlas.ragengine.security;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSVerifier;
import com.nimbusds.jose.crypto.MACVerifier;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.text.ParseException;
import java.time.Instant;
import java.util.Date;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Independently verifies the Gateway-asserted internal clearance JWT (ADR-0034 / D-P3-5(a)).
 *
 * <p>The Gateway signs a short-lived {@code X-Atlas-Internal-Clearance} JWT (HS256) with the shared
 * internal secret after it has validated the client's token. {@code rag-engine} re-verifies the
 * signature, {@code exp}, and {@code iss} here — it never simply trusts a header. A valid assertion
 * yields the caller's {@link ClearanceLevel}; anything invalid yields empty (fail closed: the caller
 * is then resolved by the existing path, which fails closed outside local/test).
 *
 * <p>The HMAC key is derived as {@code SHA-256(secret)} — byte-identical to the Gateway's
 * {@code SecurityKeys.deriveHs256} — so any operator secret length works on both sides.
 */
public class DownstreamClearanceVerifier {

    /** Header carrying the internal verified-clearance assertion. Mirrors the Gateway's signer. */
    public static final String HEADER = "X-Atlas-Internal-Clearance";

    /** Expected issuer of the internal assertion (the Gateway). */
    public static final String EXPECTED_ISSUER = "atlas-gateway";

    private static final Logger log = LoggerFactory.getLogger(DownstreamClearanceVerifier.class);

    private final byte[] key;

    public DownstreamClearanceVerifier(InternalClearanceProperties props) {
        this.key = deriveHs256(props.internalSecret());
    }

    /** Verify a serialized internal assertion → the asserted clearance, or empty if invalid/absent. */
    public Optional<ClearanceLevel> verify(String token) {
        if (token == null || token.isBlank()) {
            return Optional.empty();
        }
        try {
            SignedJWT jwt = SignedJWT.parse(token.strip());
            JWSVerifier verifier = new MACVerifier(key);
            if (!jwt.verify(verifier)) {
                log.debug("Internal clearance assertion: bad signature");
                return Optional.empty();
            }
            JWTClaimsSet claims = jwt.getJWTClaimsSet();
            Date exp = claims.getExpirationTime();
            if (exp == null || exp.toInstant().isBefore(Instant.now())) {
                log.debug("Internal clearance assertion: expired");
                return Optional.empty();
            }
            if (!EXPECTED_ISSUER.equals(claims.getIssuer())) {
                log.debug("Internal clearance assertion: wrong issuer");
                return Optional.empty();
            }
            String clearance = claims.getStringClaim("clearance");
            if (clearance == null) {
                return Optional.empty();
            }
            return Optional.of(ClearanceLevel.fromLabel(clearance));
        } catch (ParseException | JOSEException | IllegalArgumentException e) {
            log.debug("Internal clearance assertion rejected: {}", e.getMessage());
            return Optional.empty();
        }
    }

    private static byte[] deriveHs256(String secret) {
        if (secret == null || secret.isBlank()) {
            throw new IllegalArgumentException("internal HMAC secret must not be blank");
        }
        try {
            return MessageDigest.getInstance("SHA-256").digest(secret.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }
}
