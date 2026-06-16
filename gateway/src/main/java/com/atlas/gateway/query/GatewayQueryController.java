package com.atlas.gateway.query;

import com.atlas.gateway.auth.CallerClearance;
import com.atlas.gateway.auth.DownstreamClearanceSigner;
import com.atlas.gateway.router.ModelRouter;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
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
 * <p>Pipeline so far: the caller's clearance is verified by {@code JwtClearanceFilter} (ADR-0034); the
 * {@link ModelRouter} selects a cost-aware tier (ADR-0035); the controller re-asserts the verified
 * clearance + forwards the tier to {@code rag-engine}, then relays the grounded, cited answer with a
 * {@code routing} section merged into the §2.3 envelope. The semantic cache (task 5),
 * rate-limit/budget/breaker (task 6), PII redaction + sanitization (task 7), and cost metering (task 8)
 * wrap this orchestration in subsequent commits.
 */
@RestController
@RequestMapping("/v1")
public class GatewayQueryController {

    private static final Logger log = LoggerFactory.getLogger(GatewayQueryController.class);

    private final RagEngineClient ragEngine;
    private final DownstreamClearanceSigner signer;
    private final ModelRouter router;

    public GatewayQueryController(RagEngineClient ragEngine, DownstreamClearanceSigner signer,
            ModelRouter router) {
        this.ragEngine = ragEngine;
        this.signer = signer;
        this.router = router;
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

        ModelRouter.RoutingDecision decision = router.route(request.query(), http.getHeader(ModelRouter.QUALITY_HEADER));
        String assertion = signer.sign(caller.subject(), caller.clearance());
        log.info("Proxying query for '{}' at clearance '{}' via tier '{}' (escalated={})",
                caller.subject(), caller.clearance().label(), decision.tier().label(), decision.escalated());

        JsonNode answer = ragEngine.query(assertion, decision.tier().label(), request);
        return ResponseEntity.ok(withRouting(answer, decision));
    }

    /** Merge the §2.3 {@code routing} section into the relayed rag-engine response (best-effort). */
    private JsonNode withRouting(JsonNode body, ModelRouter.RoutingDecision decision) {
        if (body instanceof ObjectNode node) {
            ObjectNode routing = node.objectNode();
            routing.put("modelTier", decision.tier().label());
            routing.put("model", decision.model());
            routing.put("escalated", decision.escalated());
            node.set("routing", routing);
        }
        return body;
    }
}
