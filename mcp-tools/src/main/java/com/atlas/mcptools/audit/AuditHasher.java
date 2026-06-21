package com.atlas.mcptools.audit;

import java.time.Instant;
import org.springframework.stereotype.Component;

/**
 * Pure computation of the audit hash chain (ADR-0048). Kept free of any DB/IO so the chain math is
 * unit-testable in isolation and identical on write (in {@link AuditService}) and on verification
 * (in {@link AuditChainVerifier}).
 *
 * <p>{@code row_hash = sha256(prev_hash || US || canonical_fields)} where the canonical field string
 * is the row's logical fields joined by an ASCII unit-separator (0x1F, which cannot appear in the
 * hex digests / token ids / ISO timestamps we hash). The first row links to {@link #GENESIS}.
 */
@Component
public class AuditHasher {

    /** Genesis link for the first row in the chain (64 hex zeros). */
    public static final String GENESIS = "0".repeat(64);

    /** ASCII unit separator — an unambiguous field delimiter for canonicalization. */
    private static final char US = '\u001f';

    /** Compute the {@code row_hash} for a row given its predecessor's hash and its logical fields. */
    public String rowHash(String prevHash, Instant ts, String runId, String tool, AuditPhase phase,
            String caller, String clearance, String argsDigest, String resultRef) {
        String canonical = String.join(String.valueOf(US),
                ts.toString(), runId, tool, phase.name(), caller, clearance, argsDigest,
                resultRef == null ? "" : resultRef);
        return Digests.sha256Hex(prevHash + US + canonical);
    }

    /** Convenience overload: recompute the {@code row_hash} an existing record should have. */
    public String rowHash(AuditRecord r) {
        return rowHash(r.prevHash(), r.ts(), r.runId(), r.tool(), r.phase(),
                r.caller(), r.clearance(), r.argsDigest(), r.resultRef());
    }
}
