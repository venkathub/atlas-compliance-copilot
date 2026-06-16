package com.atlas.gateway.query;

import com.atlas.gateway.auth.CallerClearance;
import com.atlas.gateway.auth.DownstreamClearanceSigner;
import com.atlas.gateway.cache.CacheProperties;
import com.atlas.gateway.cache.QueryEmbedder;
import com.atlas.gateway.cache.SemanticCache;
import com.atlas.gateway.router.ModelRouter;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Optional;
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
 * <p>Pipeline so far: clearance verified by {@code JwtClearanceFilter} (ADR-0034) → <b>semantic-cache
 * lookup within the caller's clearance partition</b> (ADR-0036): on a hit, return the cached answer with
 * near-zero cost and <b>skip routing + the model call</b>; on a miss, the {@link ModelRouter} selects a
 * cost-aware tier (ADR-0035), the controller re-asserts the verified clearance to {@code rag-engine}, and
 * <b>trusted-writes</b> the (RBAC+guardrail+grounding-passed) answer into the cache. Rate-limit/budget/
 * breaker (task 6), PII redaction + sanitization (task 7), and cost metering (task 8) follow.
 */
@RestController
@RequestMapping("/v1")
public class GatewayQueryController {

    private static final Logger log = LoggerFactory.getLogger(GatewayQueryController.class);

    private final RagEngineClient ragEngine;
    private final DownstreamClearanceSigner signer;
    private final ModelRouter router;
    private final SemanticCache cache;
    private final QueryEmbedder embedder;
    private final CacheProperties cacheProps;
    private final ObjectMapper mapper;

    public GatewayQueryController(RagEngineClient ragEngine, DownstreamClearanceSigner signer,
            ModelRouter router, SemanticCache cache, QueryEmbedder embedder, CacheProperties cacheProps,
            ObjectMapper mapper) {
        this.ragEngine = ragEngine;
        this.signer = signer;
        this.router = router;
        this.cache = cache;
        this.embedder = embedder;
        this.cacheProps = cacheProps;
        this.mapper = mapper;
    }

    @PostMapping("/query")
    public ResponseEntity<JsonNode> query(@RequestBody(required = false) GatewayQueryRequest request,
            HttpServletRequest http) {
        if (request == null || !request.hasQuery()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "query is required");
        }
        Object attr = http.getAttribute(CallerClearance.ATTRIBUTE);
        if (!(attr instanceof CallerClearance caller)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "missing verified clearance");
        }
        String clearance = caller.clearance().label();

        // 1) Semantic-cache lookup — within the caller's clearance partition only (ADR-0036).
        float[] queryVec = null;
        if (cacheProps.enabled()) {
            queryVec = embedder.embed(request.query());
            Optional<SemanticCache.CacheHit> hit =
                    cache.lookup(clearance, cacheProps.corpusVersion(), queryVec);
            if (hit.isPresent()) {
                log.info("Semantic-cache HIT for '{}' at '{}' (sim={})",
                        caller.subject(), clearance, hit.get().similarity());
                return ResponseEntity.ok(fromCache(hit.get()));
            }
        }

        // 2) Miss → route + proxy to rag-engine with the verified clearance.
        ModelRouter.RoutingDecision decision = router.route(request.query(), http.getHeader(ModelRouter.QUALITY_HEADER));
        String assertion = signer.sign(caller.subject(), caller.clearance());
        log.info("Cache miss → proxying for '{}' at '{}' via tier '{}' (escalated={})",
                caller.subject(), clearance, decision.tier().label(), decision.escalated());
        JsonNode answer = ragEngine.query(assertion, decision.tier().label(), request);

        // 3) Trusted-write: only answers rag-engine actually returned (RBAC+guardrail+grounding-passed).
        if (cacheProps.enabled() && answer != null) {
            cache.put(clearance, cacheProps.corpusVersion(), queryVec,
                    new SemanticCache.CachedAnswer(answer.toString(), decision.model()));
        }
        return ResponseEntity.ok(withSections(answer, decision.tier().label(), decision.model(),
                decision.escalated(), false, 0.0));
    }

    /** Build the response from a cache hit: parse the stored answer + add cache/routing sections. */
    private JsonNode fromCache(SemanticCache.CacheHit hit) {
        JsonNode body;
        try {
            body = mapper.readTree(hit.answerJson());
        } catch (Exception e) {
            // A corrupt cache entry must never fail the request — treat as if absent.
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "cache decode error");
        }
        return withSections(body, "cache", hit.model(), false, true, hit.similarity());
    }

    /** Merge the §2.3 {@code routing} + {@code cache} sections into the relayed/cached response. */
    private JsonNode withSections(JsonNode body, String modelTier, String model, boolean escalated,
            boolean cacheHit, double similarity) {
        if (body instanceof ObjectNode node) {
            ObjectNode routing = node.objectNode();
            routing.put("modelTier", modelTier);
            routing.put("model", model);
            routing.put("escalated", escalated);
            node.set("routing", routing);

            ObjectNode cacheNode = node.objectNode();
            cacheNode.put("hit", cacheHit);
            if (cacheHit) {
                cacheNode.put("similarity", similarity);
            }
            node.set("cache", cacheNode);
        }
        return body;
    }
}
