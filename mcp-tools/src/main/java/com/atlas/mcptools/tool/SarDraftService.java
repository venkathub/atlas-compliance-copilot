package com.atlas.mcptools.tool;

import com.atlas.mcptools.audit.AuditPhase;
import com.atlas.mcptools.audit.AuditRecord;
import com.atlas.mcptools.audit.AuditService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Performs the governed draft-SAR write (ADR-0049): a transactional INSERT into {@code agent.sar_draft}
 * (status {@code DRAFT}) plus the {@code SUCCESS} audit row, atomically. Because {@link AuditService}
 * appends with {@code @Transactional(REQUIRED)}, the audit insert joins this transaction — so a failure
 * in either rolls back both (no orphan draft, no missing audit row).
 */
@Service
public class SarDraftService {

    private final JdbcTemplate jdbc;
    private final AuditService auditService;
    private final ObjectMapper objectMapper;

    public SarDraftService(JdbcTemplate jdbc, AuditService auditService, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.auditService = auditService;
        this.objectMapper = objectMapper;
    }

    /**
     * Create a DRAFT SAR and record the {@code SUCCESS} audit row atomically.
     *
     * @param argsDigest SHA-256 of the canonical tool args (no raw PII; LLM02) — recorded in the audit row
     */
    @Transactional
    public OpenDraftSarResult createDraft(String account, String period, String rationale,
            List<Integer> citations, String runId, String caller, String clearance, String argsDigest) {
        long ref = jdbc.queryForObject("SELECT nextval('agent.sar_draft_ref_seq')", Long.class);
        int year = OffsetDateTime.now(ZoneOffset.UTC).getYear();
        String draftRef = String.format("SAR-%d-%06d", year, ref);

        String citationsJson = toJson(citations);

        OffsetDateTime createdAt = jdbc.queryForObject(
                "INSERT INTO agent.sar_draft "
                        + "(draft_ref, account, period, rationale, citations, clearance, run_id, status) "
                        + "VALUES (?, ?, ?, ?, ?::jsonb, ?, ?, 'DRAFT') RETURNING created_at",
                OffsetDateTime.class,
                draftRef, account, period, rationale, citationsJson, clearance, runId);

        AuditRecord success = auditService.append(runId, "open_draft_sar", AuditPhase.SUCCESS,
                caller, clearance, argsDigest, draftRef);

        return new OpenDraftSarResult(
                draftRef, "DRAFT", createdAt.toInstant().toString(), "audit_" + success.seq());
    }

    private String toJson(List<Integer> citations) {
        try {
            return objectMapper.writeValueAsString(citations);
        } catch (JsonProcessingException e) {
            throw new IllegalArgumentException("citations could not be serialized to JSON", e);
        }
    }
}
