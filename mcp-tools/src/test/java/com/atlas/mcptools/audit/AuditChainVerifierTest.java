package com.atlas.mcptools.audit;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * Unit tests for the pure audit hash-chain math (ADR-0048) — no database. Covers determinism,
 * genesis linkage, and that the verifier accepts a well-formed chain and rejects both a mutated
 * field (row_hash mismatch) and a relinked row (prev_hash break).
 */
class AuditChainVerifierTest {

    private final AuditHasher hasher = new AuditHasher();
    private final AuditChainVerifier verifier = new AuditChainVerifier(null, hasher);

    private AuditRecord chained(long seq, String prevHash, AuditPhase phase, String argsDigest,
            String resultRef) {
        Instant ts = Instant.parse("2026-06-21T10:00:0" + seq + "Z");
        String rowHash = hasher.rowHash(prevHash, ts, "run_1", "open_draft_sar", phase,
                "priya", "compliance", argsDigest, resultRef);
        return new AuditRecord(seq, ts, "run_1", "open_draft_sar", phase, "priya", "compliance",
                argsDigest, resultRef, prevHash, rowHash);
    }

    private List<AuditRecord> validChain() {
        List<AuditRecord> rows = new ArrayList<>();
        AuditRecord r1 = chained(1, AuditHasher.GENESIS, AuditPhase.ATTEMPT, "d1", null);
        AuditRecord r2 = chained(2, r1.rowHash(), AuditPhase.APPROVED, "d1", null);
        AuditRecord r3 = chained(3, r2.rowHash(), AuditPhase.SUCCESS, "d1", "SAR-2026-000123");
        rows.add(r1);
        rows.add(r2);
        rows.add(r3);
        return rows;
    }

    @Test
    void hashIsDeterministic() {
        Instant ts = Instant.parse("2026-06-21T10:00:00Z");
        String a = hasher.rowHash(AuditHasher.GENESIS, ts, "r", "t", AuditPhase.ATTEMPT, "c", "compliance", "d", null);
        String b = hasher.rowHash(AuditHasher.GENESIS, ts, "r", "t", AuditPhase.ATTEMPT, "c", "compliance", "d", null);
        assertThat(a).isEqualTo(b).hasSize(64);
    }

    @Test
    void hashChangesWhenAnyFieldChanges() {
        Instant ts = Instant.parse("2026-06-21T10:00:00Z");
        String base = hasher.rowHash(AuditHasher.GENESIS, ts, "r", "t", AuditPhase.ATTEMPT, "c", "compliance", "d", null);
        String diff = hasher.rowHash(AuditHasher.GENESIS, ts, "r", "t", AuditPhase.SUCCESS, "c", "compliance", "d", null);
        assertThat(diff).isNotEqualTo(base);
    }

    @Test
    void emptyChainIsVacuouslyValid() {
        assertThat(verifier.verifyChain(List.of()).valid()).isTrue();
    }

    @Test
    void wellFormedChainVerifies() {
        AuditChainVerifier.VerificationResult result = verifier.verifyChain(validChain());
        assertThat(result.valid()).isTrue();
        assertThat(result.brokenSeq()).isNull();
    }

    @Test
    void firstRowMustLinkToGenesis() {
        List<AuditRecord> rows = validChain();
        AuditRecord bad = chained(1, "deadbeef".repeat(8), AuditPhase.ATTEMPT, "d1", null);
        rows.set(0, bad);
        AuditChainVerifier.VerificationResult result = verifier.verifyChain(rows);
        assertThat(result.valid()).isFalse();
        assertThat(result.brokenSeq()).isEqualTo(1L);
    }

    @Test
    void mutatedFieldBreaksRowHash() {
        List<AuditRecord> rows = validChain();
        AuditRecord r2 = rows.get(1);
        // Simulate tampering: change a field but keep the stored row_hash (as a DB UPDATE would).
        AuditRecord tampered = new AuditRecord(r2.seq(), r2.ts(), r2.runId(), r2.tool(), r2.phase(),
                "mallory", r2.clearance(), r2.argsDigest(), r2.resultRef(), r2.prevHash(), r2.rowHash());
        rows.set(1, tampered);
        AuditChainVerifier.VerificationResult result = verifier.verifyChain(rows);
        assertThat(result.valid()).isFalse();
        assertThat(result.brokenSeq()).isEqualTo(2L);
        assertThat(result.message()).contains("row_hash");
    }

    @Test
    void relinkedRowBreaksChain() {
        List<AuditRecord> rows = validChain();
        // Recompute row 3 against the wrong predecessor: its prev_hash no longer matches row 2.
        AuditRecord r3 = rows.get(2);
        AuditRecord relinked = new AuditRecord(r3.seq(), r3.ts(), r3.runId(), r3.tool(), r3.phase(),
                r3.caller(), r3.clearance(), r3.argsDigest(), r3.resultRef(),
                "0".repeat(64), r3.rowHash());
        rows.set(2, relinked);
        AuditChainVerifier.VerificationResult result = verifier.verifyChain(rows);
        assertThat(result.valid()).isFalse();
        assertThat(result.brokenSeq()).isEqualTo(3L);
        assertThat(result.message()).contains("prev_hash");
    }
}
