package com.atlas.gateway.query;

import com.atlas.gateway.auth.CallerClearance;
import com.atlas.gateway.auth.DownstreamClearanceSigner;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/**
 * {@code POST /v1/query} — the public query entry point (P3_SPEC §2.5).
 *
 * <p>Task 3 (this commit) implements the authenticated pass-through: the caller's clearance has already
 * been verified by {@code JwtClearanceFilter} (ADR-0034); the controller re-asserts it to {@code rag-engine}
 * via a signed internal assertion and relays the grounded, cited answer. The router (task 4), semantic
 * cache (task 5), rate-limit/budget/breaker (task 6), PII redaction + output sanitization (task 7), and
 * cost metering (task 8) wrap this orchestration in subsequent commits.
 */
@RestController
@RequestMapping("/v1")
public class GatewayQueryController {

    private static final Logger log = LoggerFactory.getLogger(GatewayQueryController.class);

    private final RagEngineClient ragEngine;
    private final DownstreamClearanceSigner signer;

    public GatewayQueryController(RagEngineClient ragEngine, DownstreamClearanceSigner signer) {
        this.ragEngine = ragEngine;
        this.signer = signer;
    }

    @PostMapping("/query")
    public ResponseEntity<JsonNode> query(@RequestBody(required = false) GatewayQueryRequest request,
            HttpServletRequest http) {
        if (request == null || !request.hasQuery()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "query is required");
        }
        // The filter guarantees this on protected routes; defend in depth.
        Object attr = http.getAttribute(CallerClearance.ATTRIBUTE);
        if (!(attr instanceof CallerClearance caller)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "missing verified clearance");
        }
        String assertion = signer.sign(caller.subject(), caller.clearance());
        log.info("Proxying query for '{}' at clearance '{}'", caller.subject(), caller.clearance().label());
        JsonNode answer = ragEngine.query(assertion, request);
        return ResponseEntity.ok(answer);
    }
}
