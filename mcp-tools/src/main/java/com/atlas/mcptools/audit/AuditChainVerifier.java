package com.atlas.mcptools.audit;

import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Component;

/**
 * Recomputes the {@code agent.tool_audit} hash chain and flags any break (ADR-0048, ROADMAP §6 G9).
 *
 * <p>The append-only DB grant + trigger make the log tamper-<em>resistant</em>; this verifier makes
 * it tamper-<em>evident</em>: if a privileged actor disables the guard and rewrites a row, the
 * recomputed chain no longer matches and the first broken {@code seq} is reported.
 */
@Component
public class AuditChainVerifier {

    /** Outcome of a chain verification. {@code brokenSeq} is the first offending row (null if valid). */
    public record VerificationResult(boolean valid, Long brokenSeq, String message) {
        static VerificationResult ok(int rows) {
            return new VerificationResult(true, null, "chain verified (" + rows + " rows)");
        }

        static VerificationResult broken(long seq, String why) {
            return new VerificationResult(false, seq, "chain broken at seq=" + seq + ": " + why);
        }
    }

    private static final RowMapper<AuditRecord> MAPPER = (rs, n) -> new AuditRecord(
            rs.getLong("seq"),
            rs.getObject("ts", OffsetDateTime.class).toInstant(),
            rs.getString("run_id"),
            rs.getString("tool"),
            AuditPhase.valueOf(rs.getString("phase")),
            rs.getString("caller"),
            rs.getString("clearance"),
            rs.getString("args_digest"),
            rs.getString("result_ref"),
            rs.getString("prev_hash"),
            rs.getString("row_hash"));

    private final JdbcTemplate jdbc;
    private final AuditHasher hasher;

    public AuditChainVerifier(JdbcTemplate jdbc, AuditHasher hasher) {
        this.jdbc = jdbc;
        this.hasher = hasher;
    }

    /** Read the whole log (ordered by seq) and verify the chain. */
    public VerificationResult verify() {
        List<AuditRecord> rows = jdbc.query(
                "SELECT seq, ts, run_id, tool, phase, caller, clearance, args_digest, result_ref, "
                        + "prev_hash, row_hash FROM agent.tool_audit ORDER BY seq",
                MAPPER);
        return verifyChain(rows);
    }

    /** Pure verification over an ordered (by seq) list — unit-testable without a database. */
    public VerificationResult verifyChain(List<AuditRecord> rows) {
        String expectedPrev = AuditHasher.GENESIS;
        for (AuditRecord r : rows) {
            if (!expectedPrev.equals(r.prevHash())) {
                return VerificationResult.broken(r.seq(),
                        "prev_hash does not link to the previous row's row_hash");
            }
            String recomputed = hasher.rowHash(r);
            if (!recomputed.equals(r.rowHash())) {
                return VerificationResult.broken(r.seq(), "row_hash does not match recomputed digest");
            }
            expectedPrev = r.rowHash();
        }
        return VerificationResult.ok(rows.size());
    }
}
