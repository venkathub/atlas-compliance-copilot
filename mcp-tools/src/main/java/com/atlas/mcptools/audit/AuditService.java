package com.atlas.mcptools.audit;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Appends immutable, hash-chained rows to {@code agent.tool_audit} (ADR-0048).
 *
 * <p>Each append is serialized via a transaction-scoped Postgres advisory lock so the chain stays
 * strictly linear under concurrency (low-volume governed writes — correctness over throughput). The
 * application sets {@code ts} (truncated to microseconds, Postgres's resolution) so the stored value
 * round-trips exactly and the {@code row_hash} is reproducible by {@link AuditChainVerifier}.
 *
 * <p>Callers pass an {@code argsDigest} (a SHA-256 of the canonical tool args) — never raw PII (LLM02).
 */
@Service
public class AuditService {

    /** Constant key for the chain-append advisory lock (arbitrary, app-wide). */
    private static final long CHAIN_LOCK_KEY = 0x4154_4C41_5341_5544L; // "ATLASAUD"

    private final JdbcTemplate jdbc;
    private final AuditHasher hasher;

    public AuditService(JdbcTemplate jdbc, AuditHasher hasher) {
        this.jdbc = jdbc;
        this.hasher = hasher;
    }

    /** Append one audit row for a governed tool invocation. Returns the persisted record. */
    @Transactional
    public AuditRecord append(String runId, String tool, AuditPhase phase, String caller,
            String clearance, String argsDigest, String resultRef) {
        // Serialize chain appends for the duration of this transaction.
        jdbc.query("SELECT pg_advisory_xact_lock(?)",
                ps -> ps.setLong(1, CHAIN_LOCK_KEY), rs -> null);

        String prevHash = jdbc.query(
                "SELECT row_hash FROM agent.tool_audit ORDER BY seq DESC LIMIT 1",
                rs -> rs.next() ? rs.getString(1) : AuditHasher.GENESIS);

        Instant ts = Instant.now().truncatedTo(ChronoUnit.MICROS);
        String rowHash = hasher.rowHash(prevHash, ts, runId, tool, phase, caller, clearance,
                argsDigest, resultRef);

        Long seq = jdbc.queryForObject(
                "INSERT INTO agent.tool_audit "
                        + "(ts, run_id, tool, phase, caller, clearance, args_digest, result_ref, "
                        + "prev_hash, row_hash) "
                        + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING seq",
                Long.class,
                OffsetDateTime.ofInstant(ts, ZoneOffset.UTC),
                runId, tool, phase.name(), caller, clearance, argsDigest, resultRef,
                prevHash, rowHash);

        return new AuditRecord(seq, ts, runId, tool, phase, caller, clearance, argsDigest,
                resultRef, prevHash, rowHash);
    }
}
