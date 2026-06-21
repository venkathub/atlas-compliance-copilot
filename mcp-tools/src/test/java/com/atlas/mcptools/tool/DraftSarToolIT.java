package com.atlas.mcptools.tool;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.atlas.mcptools.AbstractAgentSchemaIT;
import com.atlas.mcptools.audit.AuditChainVerifier;
import com.atlas.mcptools.auth.InsufficientClearanceException;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

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
        authenticateAs("priya", "compliance");
    }

    @AfterEach
    void clearContext() {
        SecurityContextHolder.clearContext();
    }

    /** Place a validated-JWT principal in the security context (as the resource-server filter would). */
    private static void authenticateAs(String subject, String clearance) {
        Jwt jwt = Jwt.withTokenValue("test-token")
                .header("alg", "HS256")
                .subject(subject)
                .claim("clearance", clearance)
                .issuedAt(Instant.now().minusSeconds(5))
                .expiresAt(Instant.now().plusSeconds(3600))
                .build();
        SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(jwt));
    }

    @Test
    void createsDraftWithAttemptAndAtomicSuccessAudit() {
        OpenDraftSarResult result = tool.openDraftSar(
                "Northwind", "2026-Q2", "Exception #2 exceeds threshold", List.of(1, 2), "run_1");

        assertThat(result.status()).isEqualTo("DRAFT");
        assertThat(result.draftRef()).matches("SAR-\\d{4}-\\d{6}");
        assertThat(result.createdAt()).isNotBlank();
        assertThat(result.auditRef()).matches("audit_\\d+");

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

    @Test
    void subComplianceCallerIsDeniedWithNoWrite() {
        authenticateAs("analyst-bob", "analyst"); // below the required 'compliance'

        assertThatThrownBy(() -> tool.openDraftSar(
                "Northwind", "2026-Q2", "exceeds", List.of(1, 2), "run_1"))
                .isInstanceOf(InsufficientClearanceException.class);

        // No draft, and the audit records ATTEMPT then DENIED (LLM06 / ASI03).
        assertThat(appJdbc.queryForObject("SELECT count(*) FROM agent.sar_draft", Integer.class)).isZero();
        List<String> phases = appJdbc.queryForList(
                "SELECT phase FROM agent.tool_audit ORDER BY seq", String.class);
        assertThat(phases).containsExactly("ATTEMPT", "DENIED");
        assertThat(verifier.verify().valid()).isTrue();
    }
}
