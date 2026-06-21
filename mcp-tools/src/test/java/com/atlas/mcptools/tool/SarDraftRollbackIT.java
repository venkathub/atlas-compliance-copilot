package com.atlas.mcptools.tool;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;

import com.atlas.mcptools.AbstractAgentSchemaIT;
import com.atlas.mcptools.audit.AuditPhase;
import com.atlas.mcptools.audit.AuditService;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

/**
 * Atomicity IT (ADR-0049): if the {@code SUCCESS} audit insert fails inside {@link SarDraftService},
 * the whole transaction rolls back — leaving no orphan {@code sar_draft} row. The audit append joins
 * the same transaction, so the draft + audit are all-or-nothing.
 */
@SpringBootTest
class SarDraftRollbackIT extends AbstractAgentSchemaIT {

    @Autowired
    SarDraftService sarDraftService;

    @Autowired
    JdbcTemplate appJdbc;

    @MockitoBean
    AuditService auditService;

    @BeforeEach
    void reset() {
        new JdbcTemplate(new DriverManagerDataSource(
                POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword()))
                .update("DELETE FROM agent.sar_draft");
    }

    @Test
    void failedSuccessAuditRollsBackTheDraft() {
        given(auditService.append(any(), any(), eq(AuditPhase.SUCCESS), any(), any(), any(), any()))
                .willThrow(new RuntimeException("audit write failed"));

        assertThatThrownBy(() -> sarDraftService.createDraft(
                "Northwind", "2026-Q2", "exceeds", List.of(1), "run_1", "priya", "compliance", "digest"))
                .isInstanceOf(RuntimeException.class);

        Integer drafts = appJdbc.queryForObject("SELECT count(*) FROM agent.sar_draft", Integer.class);
        assertThat(drafts).as("no orphan draft after the atomic write rolled back").isZero();
    }
}
