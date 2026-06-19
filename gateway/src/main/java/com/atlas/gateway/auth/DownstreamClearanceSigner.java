package com.atlas.gateway.auth;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.time.Instant;
import java.util.Date;

/**
 * Signs the Gateway→{@code rag-engine} internal verified-clearance assertion (ADR-0034 / D-P3-5(a)).
 *
 * <p>After the Gateway validates the client JWT and resolves the caller's clearance, it re-asserts that
 * clearance to {@code rag-engine} as a short-lived JWT signed with the <em>separate</em> shared internal
 * secret ({@code SHA-256(ATLAS_GATEWAY_INTERNAL_SECRET)}). {@code rag-engine} independently verifies it
 * (defense-in-depth) and ignores any client-set {@code X-Atlas-Clearance} on this path. The assertion is
 * deliberately short-lived (it is minted per downstream call, not handed to clients).
 *
 * <p>The serialized token is carried to {@code rag-engine} in the {@link #HEADER} request header by the
 * query path (P3 task 3).
 */
public class DownstreamClearanceSigner {

    /** Header carrying the internal verified-clearance assertion on the Gateway→rag-engine hop. */
    public static final String HEADER = "X-Atlas-Internal-Clearance";

    /** Issuer claim of the internal assertion (distinct from the client-facing IdP issuer). */
    public static final String ISSUER = "atlas-gateway";

    private static final long TTL_SECONDS = 60L; // short-lived; minted per downstream call

    private final byte[] key;

    public DownstreamClearanceSigner(GatewayProperties props) {
        this.key = SecurityKeys.deriveHs256(props.internalSecret());
    }

    /** Mint a signed internal assertion of {@code subject} at {@code clearance}. */
    public String sign(String subject, Clearance clearance) {
        Instant now = Instant.now();
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .subject(subject)
                .claim("clearance", clearance.label())
                .issuer(ISSUER)
                .issueTime(Date.from(now))
                .expirationTime(Date.from(now.plusSeconds(TTL_SECONDS)))
                .build();
        try {
            SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
            jwt.sign(new MACSigner(key));
            return jwt.serialize();
        } catch (JOSEException e) {
            throw new IllegalStateException("Failed to sign internal clearance assertion", e);
        }
    }
}
