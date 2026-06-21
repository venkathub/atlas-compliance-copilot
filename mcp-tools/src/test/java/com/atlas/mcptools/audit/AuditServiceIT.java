package com.atlas.mcptools.audit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.atlas.mcptools.AbstractAgentSchemaIT;
import javax.sql.DataSource;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

/**
 * Audit-log IT (ADR-0048) against a real postgres:16 container (shared {@link AbstractAgentSchemaIT}).
 * Proves the append-only contract end-to-end: the migration creates the least-privilege role + trigger;
 * {@link AuditService} builds a valid hash chain; UPDATE/DELETE are denied for the app role (GRANT) AND
 * the owner (trigger); and the {@link AuditChainVerifier} detects a row tampered with after the guard is
 * bypassed.
 *
 * <p>Flyway runs as the container superuser (privileged); the Spring runtime datasource connects as the
 * restricted {@code atlas_mcp_app} role — the honest production separation.
 */
@SpringBootTest
class AuditServiceIT extends AbstractAgentSchemaIT {

    @Autowired
    AuditService auditService;

    @Autowired
    AuditChainVerifier verifier;

    /** App-role JdbcTemplate (the autowired runtime datasource). */
    @Autowired
    JdbcTemplate appJdbc;

    /** Owner/superuser JdbcTemplate — used to inspect privileges and to simulate a malicious DBA. */
    private JdbcTemplate ownerJdbc;

    @BeforeEach
    void setUp() {
        DataSource owner = new DriverManagerDataSource(
                POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
        ownerJdbc = new JdbcTemplate(owner);
        // TRUNCATE does not fire the row-level UPDATE/DELETE guard; RESTART IDENTITY keeps tests
        // independent (each starts an empty chain from GENESIS, seq from 1).
        ownerJdbc.execute("TRUNCATE agent.tool_audit RESTART IDENTITY");
    }

    @Test
    void migrationCreatesRestrictedRoleAndTrigger() {
        Boolean roleExists = ownerJdbc.queryForObject(
                "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ?)", Boolean.class, APP_ROLE);
        assertThat(roleExists).isTrue();

        Boolean canInsert = ownerJdbc.queryForObject(
                "SELECT has_table_privilege(?, 'agent.tool_audit', 'INSERT')", Boolean.class, APP_ROLE);
        Boolean canSelect = ownerJdbc.queryForObject(
                "SELECT has_table_privilege(?, 'agent.tool_audit', 'SELECT')", Boolean.class, APP_ROLE);
        Boolean canUpdate = ownerJdbc.queryForObject(
                "SELECT has_table_privilege(?, 'agent.tool_audit', 'UPDATE')", Boolean.class, APP_ROLE);
        Boolean canDelete = ownerJdbc.queryForObject(
                "SELECT has_table_privilege(?, 'agent.tool_audit', 'DELETE')", Boolean.class, APP_ROLE);
        assertThat(canInsert).isTrue();
        assertThat(canSelect).isTrue();
        assertThat(canUpdate).as("UPDATE not granted to app role").isFalse();
        assertThat(canDelete).as("DELETE not granted to app role").isFalse();

        Integer triggers = ownerJdbc.queryForObject(
                "SELECT count(*) FROM pg_trigger WHERE tgrelid = 'agent.tool_audit'::regclass "
                        + "AND NOT tgisinternal", Integer.class);
        assertThat(triggers).isGreaterThanOrEqualTo(1);
    }

    @Test
    void appendBuildsAValidHashChain() {
        AuditRecord r1 = auditService.append("run_1", "open_draft_sar", AuditPhase.ATTEMPT,
                "priya", "compliance", Digests.sha256Hex("args"), null);
        AuditRecord r2 = auditService.append("run_1", "open_draft_sar", AuditPhase.APPROVED,
                "priya", "compliance", Digests.sha256Hex("args"), null);
        AuditRecord r3 = auditService.append("run_1", "open_draft_sar", AuditPhase.SUCCESS,
                "priya", "compliance", Digests.sha256Hex("args"), "SAR-2026-000123");

        assertThat(r1.prevHash()).isEqualTo(AuditHasher.GENESIS);
        assertThat(r2.prevHash()).isEqualTo(r1.rowHash());
        assertThat(r3.prevHash()).isEqualTo(r2.rowHash());
        assertThat(r3.resultRef()).isEqualTo("SAR-2026-000123");

        AuditChainVerifier.VerificationResult result = verifier.verify();
        assertThat(result.valid()).as(result.message()).isTrue();
    }

    @Test
    void appRoleCannotUpdateOrDelete() {
        auditService.append("run_1", "open_draft_sar", AuditPhase.ATTEMPT,
                "priya", "compliance", Digests.sha256Hex("args"), null);

        assertThatThrownBy(() -> appJdbc.update("UPDATE agent.tool_audit SET caller = 'x'"))
                .isInstanceOf(DataAccessException.class);
        assertThatThrownBy(() -> appJdbc.update("DELETE FROM agent.tool_audit"))
                .isInstanceOf(DataAccessException.class);
    }

    @Test
    void ownerCannotUpdateOrDeleteThroughTrigger() {
        auditService.append("run_1", "open_draft_sar", AuditPhase.ATTEMPT,
                "priya", "compliance", Digests.sha256Hex("args"), null);

        // The owner keeps UPDATE/DELETE *privilege* but the trigger refuses the operation.
        assertThatThrownBy(() -> ownerJdbc.update("UPDATE agent.tool_audit SET caller = 'x'"))
                .isInstanceOf(DataAccessException.class)
                .hasMessageContaining("append-only");
        assertThatThrownBy(() -> ownerJdbc.update("DELETE FROM agent.tool_audit WHERE seq > 0"))
                .isInstanceOf(DataAccessException.class)
                .hasMessageContaining("append-only");
    }

    @Test
    void tamperingAfterDisablingTheGuardIsDetected() {
        auditService.append("run_1", "open_draft_sar", AuditPhase.ATTEMPT,
                "priya", "compliance", Digests.sha256Hex("args"), null);
        AuditRecord target = auditService.append("run_1", "open_draft_sar", AuditPhase.APPROVED,
                "priya", "compliance", Digests.sha256Hex("args"), null);
        assertThat(verifier.verify().valid()).isTrue();

        // Simulate a privileged actor rewriting history: disable the guard, mutate, re-enable.
        ownerJdbc.execute("ALTER TABLE agent.tool_audit DISABLE TRIGGER tool_audit_append_only");
        ownerJdbc.update("UPDATE agent.tool_audit SET caller = 'mallory' WHERE seq = ?", target.seq());
        ownerJdbc.execute("ALTER TABLE agent.tool_audit ENABLE TRIGGER tool_audit_append_only");

        AuditChainVerifier.VerificationResult result = verifier.verify();
        assertThat(result.valid()).isFalse();
        assertThat(result.brokenSeq()).isEqualTo(target.seq());
    }
}
