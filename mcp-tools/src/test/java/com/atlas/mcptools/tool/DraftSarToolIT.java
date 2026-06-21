package com.atlas.mcptools.tool;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.atlas.mcptools.AbstractAgentSchemaIT;
import com.atlas.mcptools.audit.AuditChainVerifier;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

/**
 * Contract IT for the governed draft-SAR write (ADR-0049): the tool writes ATTEMPT then a
 * transactional sar_draft + SUCCESS audit row; invalid input is rejected with no write; and the
 * audit chain stays valid throughout.
 */
@SpringBootTest
class DraftSarToolIT extends AbstractAgentSchemaIT {

    @Autowired
    DraftSarTool tool;

    @Autowired
    AuditChainVerifier verifier;

    @Autowired
    JdbcTemplate appJdbc;

    private JdbcTemplate ownerJdbc;

    @BeforeEach
    void reset() {
        ownerJdbc = new JdbcTemplate(new DriverManagerDataSource(
                POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword()));
        ownerJdbc.update("DELETE FROM agent.sar_draft");
        ownerJdbc.execute("TRUNCATE agent.tool_audit RESTART IDENTITY");
    }

    @Test
    void createsDraftWithAttemptAndAtomicSuccessAudit() {
        OpenDraftSarResult result = tool.openDraftSar(
                "Northwind", "2026-Q2", "Exception #2 exceeds threshold", List.of(1, 2), "run_1");

        assertThat(result.status()).isEqualTo("DRAFT");
        assertThat(result.draftRef()).matches("SAR-\\d{4}-\\d{6}");
        assertThat(result.createdAt()).isNotBlank();

        // sar_draft row persisted with provenance.
        Map<String, Object> row = appJdbc.queryForMap(
                "SELECT draft_ref, account, period, rationale, citations, clearance, run_id, status "
                        + "FROM agent.sar_draft WHERE draft_ref = ?", result.draftRef());
        assertThat(row).containsEntry("account", "Northwind")
                .containsEntry("period", "2026-Q2")
                .containsEntry("run_id", "run_1")
                .containsEntry("status", "DRAFT")
                .containsEntry("clearance", "compliance");
        assertThat(row.get("citations").toString()).contains("1").contains("2");

        // Audit: ATTEMPT then SUCCESS (result_ref = draftRef); chain valid.
        List<Map<String, Object>> audit = appJdbc.queryForList(
                "SELECT phase, result_ref FROM agent.tool_audit ORDER BY seq");
        assertThat(audit).hasSize(2);
        assertThat(audit.get(0)).containsEntry("phase", "ATTEMPT");
        assertThat(audit.get(1)).containsEntry("phase", "SUCCESS")
                .containsEntry("result_ref", result.draftRef());
        assertThat(verifier.verify().valid()).isTrue();
    }

    @Test
    void invalidPeriodIsRejectedWithNoDraftAndAnErrorAudit() {
        assertThatThrownBy(() -> tool.openDraftSar(
                "Northwind", "2026Q2", "bad period", List.of(1), "run_1"))
                .isInstanceOf(IllegalArgumentException.class);

        Integer drafts = appJdbc.queryForObject("SELECT count(*) FROM agent.sar_draft", Integer.class);
        assertThat(drafts).isZero();

        List<String> phases = appJdbc.queryForList(
                "SELECT phase FROM agent.tool_audit ORDER BY seq", String.class);
        assertThat(phases).containsExactly("ATTEMPT", "ERROR");
        assertThat(verifier.verify().valid()).isTrue();
    }

    @Test
    void oversizedRationaleIsRejected() {
        String big = "x".repeat(SarInputValidator.MAX_RATIONALE_LEN + 1);
        assertThatThrownBy(() -> tool.openDraftSar("Northwind", "2026-Q2", big, List.of(1), "run_1"))
                .isInstanceOf(IllegalArgumentException.class);
        assertThat(appJdbc.queryForObject("SELECT count(*) FROM agent.sar_draft", Integer.class)).isZero();
    }
}
