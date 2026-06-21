package com.atlas.mcptools.tool;

import com.atlas.mcptools.audit.AuditPhase;
import com.atlas.mcptools.audit.AuditService;
import com.atlas.mcptools.audit.Digests;
import com.atlas.mcptools.auth.ClearanceRecheck;
import com.atlas.mcptools.auth.InsufficientClearanceException;
import com.atlas.mcptools.tool.ToolCallerContext.CallerIdentity;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springaicommunity.mcp.annotation.McpTool;
import org.springaicommunity.mcp.annotation.McpToolParam;
import org.springframework.stereotype.Component;

/**
 * The single governed write tool (P4_SPEC §1, ADR-0049): {@code open_draft_sar} creates a DRAFT
 * Suspicious Activity Report for human review. It is exposed over MCP Streamable HTTP via the
 * annotation model (auto-discovered by the Spring AI MCP server) and returns structured output.
 *
 * <p>Governance layered across P4: the transactional write + atomic audit (this task); the OAuth 2.1
 * per-call clearance re-check (task 4, via {@link ToolCallerContext}); and the single-use, graph-bound
 * approval precondition (task 5). The authoritative human-in-the-loop gate lives in the agent graph
 * (task 8); this tool's checks are defense-in-depth.
 */
@Component
public class DraftSarTool {

    private static final Logger log = LoggerFactory.getLogger(DraftSarTool.class);
    private static final String TOOL = "open_draft_sar";
    private static final char US = '\u001f';

    private final SarDraftService sarDraftService;
    private final AuditService auditService;
    private final ToolCallerContext callerContext;
    private final ClearanceRecheck clearanceRecheck;

    public DraftSarTool(SarDraftService sarDraftService, AuditService auditService,
            ToolCallerContext callerContext, ClearanceRecheck clearanceRecheck) {
        this.sarDraftService = sarDraftService;
        this.auditService = auditService;
        this.callerContext = callerContext;
        this.clearanceRecheck = clearanceRecheck;
    }

    @McpTool(
            name = TOOL,
            description = "Create a DRAFT Suspicious Activity Report for human review. Never auto-files.",
            generateOutputSchema = true)
    public OpenDraftSarResult openDraftSar(
            @McpToolParam(required = true, description = "Account the SAR concerns") String account,
            @McpToolParam(required = true, description = "Reporting period, e.g. 2026-Q2") String period,
            @McpToolParam(required = true, description = "Why the report is being opened") String rationale,
            @McpToolParam(required = true, description = "Source citation numbers grounding the SAR")
                    List<Integer> citations,
            @McpToolParam(required = true, description = "Originating agent run id") String runId) {

        CallerIdentity id = callerContext.current();
        String argsDigest = Digests.sha256Hex(argsCanonical(account, period, rationale, citations));

        auditService.append(runId, TOOL, AuditPhase.ATTEMPT, id.caller(), id.clearance(), argsDigest, null);

        // Per-call authorization re-check (LLM06 / ASI03) — independent of P1 RBAC and the token's
        // validity. A caller below the required clearance is refused here, not at the HTTP layer.
        try {
            clearanceRecheck.require(id.clearance());
        } catch (InsufficientClearanceException e) {
            auditService.append(runId, TOOL, AuditPhase.DENIED, id.caller(), id.clearance(), argsDigest, null);
            log.warn("open_draft_sar DENIED for caller {} ({}): {}", id.caller(), id.clearance(), e.getMessage());
            throw e;
        }

        try {
            SarInputValidator.validate(account, period, rationale, citations);
            OpenDraftSarResult result = sarDraftService.createDraft(
                    account, period, rationale, citations, runId, id.caller(), id.clearance(), argsDigest);
            log.info("open_draft_sar created {} for account {} (run {})",
                    result.draftRef(), account, runId);
            return result;
        } catch (RuntimeException e) {
            auditService.append(runId, TOOL, AuditPhase.ERROR, id.caller(), id.clearance(),
                    argsDigest, null);
            throw e;
        }
    }

    private static String argsCanonical(String account, String period, String rationale,
            List<Integer> citations) {
        return String.join(String.valueOf(US),
                account, period, rationale, String.valueOf(citations));
    }
}
