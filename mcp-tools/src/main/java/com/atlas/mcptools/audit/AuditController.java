package com.atlas.mcptools.audit;

import com.atlas.mcptools.auth.ClearanceRecheck;
import com.atlas.mcptools.auth.InsufficientClearanceException;
import com.atlas.mcptools.tool.ToolCallerContext;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Read-only, compliance-gated audit query endpoint (P5 Task 5 — the admin "Audit" view).
 *
 * <p>{@code GET /v1/audit} returns a page of governed-action audit rows plus a global
 * {@code chainVerified} flag. It is <b>SELECT-only</b> (no write path; the append-only chain stays
 * owned by {@link AuditService}) and refuses callers below the required clearance (default
 * {@code compliance}, via {@link ClearanceRecheck}) — the same OAuth 2.1 resource server that guards the
 * {@code /mcp} tool validates the Bearer token. Only non-sensitive columns are surfaced (LLM02).
 *
 * <p>Filters: {@code caller} and {@code runId} (both indexed). The {@code account} of a SAR is not a
 * stored column — it lives only inside the hashed {@code args_digest} (LLM02) — so it is not filterable
 * here without touching the frozen write path.
 */
@RestController
@RequestMapping("/v1/audit")
public class AuditController {

    private static final int DEFAULT_SIZE = 25;
    private static final int MAX_SIZE = 100;

    private final AuditQueryDao dao;
    private final AuditChainVerifier verifier;
    private final ClearanceRecheck clearanceRecheck;
    private final ToolCallerContext callerContext;

    public AuditController(AuditQueryDao dao, AuditChainVerifier verifier,
            ClearanceRecheck clearanceRecheck, ToolCallerContext callerContext) {
        this.dao = dao;
        this.verifier = verifier;
        this.clearanceRecheck = clearanceRecheck;
        this.callerContext = callerContext;
    }

    @GetMapping
    public AuditPageResponse query(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "25") int size,
            @RequestParam(required = false) String caller,
            @RequestParam(required = false) String runId) {

        // Per-request clearance re-check (refuse < compliance), independent of token validation —
        // the token is valid, but reading the governed-action audit demands compliance+.
        clearanceRecheck.require(callerContext.current().clearance());

        int safeSize = Math.min(Math.max(size, 1), MAX_SIZE);
        int safePage = Math.max(page, 0);
        long offset = Math.min((long) safePage * safeSize, Integer.MAX_VALUE);
        long total = dao.count(caller, runId);
        List<AuditRowView> rows = dao.page(caller, runId, safeSize, (int) offset);
        boolean chainVerified = verifier.verify().valid();
        return new AuditPageResponse(safePage, safeSize, total, chainVerified, rows);
    }

    /** Valid token but insufficient clearance → 403 (not 401: authenticated, just not authorized). */
    @ExceptionHandler(InsufficientClearanceException.class)
    public ResponseEntity<Map<String, String>> onInsufficientClearance(InsufficientClearanceException e) {
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(Map.of("error", "forbidden", "reason", e.getMessage()));
    }
}
