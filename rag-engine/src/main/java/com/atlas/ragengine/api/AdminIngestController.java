package com.atlas.ragengine.api;

import com.atlas.ragengine.ingest.IngestionService;
import com.atlas.ragengine.ingest.IngestionService.IngestionReport;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.ClearanceResolver;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/**
 * {@code POST /v1/admin/ingest} — triggers a full corpus rebuild. Guarded by the P1 clearance shim:
 * only a {@code RESTRICTED} (admin) caller may invoke it (ADR-0016). Superseded by real authz in P3.
 */
@RestController
@RequestMapping("/v1/admin")
public class AdminIngestController {

    private static final Logger log = LoggerFactory.getLogger(AdminIngestController.class);

    private final IngestionService ingestionService;
    private final ClearanceResolver clearanceResolver;

    public AdminIngestController(IngestionService ingestionService, ClearanceResolver clearanceResolver) {
        this.ingestionService = ingestionService;
        this.clearanceResolver = clearanceResolver;
    }

    @PostMapping("/ingest")
    public ResponseEntity<IngestionReport> ingest(HttpServletRequest http) {
        ClearanceLevel caller = clearanceResolver.resolve(HttpRequestHeaders.of(http));
        if (caller != ClearanceLevel.RESTRICTED) {
            log.warn("Rejected admin ingest from caller '{}' (requires restricted/admin)", caller.label());
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "admin ingest requires restricted clearance");
        }
        IngestionReport report = ingestionService.rebuild();
        log.info("Admin ingest by '{}': {}", caller.label(), report);
        return ResponseEntity.ok(report);
    }
}
