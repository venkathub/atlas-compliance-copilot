package com.atlas.gateway.query;

import com.atlas.gateway.auth.CallerClearance;
import com.atlas.gateway.auth.DownstreamClearanceSigner;
import com.atlas.gateway.cache.CacheProperties;
import com.atlas.gateway.cache.QueryEmbedder;
import com.atlas.gateway.cache.SemanticCache;
import com.atlas.gateway.router.CostTable;
import com.atlas.gateway.router.ModelRouter;
import com.atlas.gateway.router.ModelTier;
import com.atlas.gateway.resilience.BudgetGuard;
import com.atlas.gateway.resilience.ModelCircuitBreaker;
import com.atlas.gateway.resilience.RateLimiter;
import com.atlas.gateway.resilience.RequestLimits;
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
 * <p>Pipeline: clearance verified by {@code JwtClearanceFilter} (ADR-0034) → <b>rate limit</b> (429) →
 * <b>budget pre-check</b> (402) → <b>input-size cap</b> (413) → <b>semantic-cache lookup</b> within the
 * caller's clearance partition (ADR-0036; a hit skips the model call) → <b>cost-aware routing</b>
 * (ADR-0035) → downstream call <b>wrapped in the circuit breaker</b> + read timeout (ADR-0039; 503
 * fallback) → <b>trusted-write</b> + <b>budget post-accounting</b>. PII redaction + sanitization (task 7)
 * and full cost metering (task 8) follow. (LLM10 resource controls: ADR-0038.)
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
    private final RateLimiter rateLimiter;
    private final BudgetGuard budgetGuard;
    private final RequestLimits requestLimits;
    private final ModelCircuitBreaker circuitBreaker;
    private final CostTable costTable;
    private final ObjectMapper mapper;

    public GatewayQueryController(RagEngineClient ragEngine, DownstreamClearanceSigner signer,
            ModelRouter router, SemanticCache cache, QueryEmbedder embedder, CacheProperties cacheProps,
            RateLimiter rateLimiter, BudgetGuard budgetGuard, RequestLimits requestLimits,
            ModelCircuitBreaker circuitBreaker, CostTable costTable, ObjectMapper mapper) {
        this.ragEngine = ragEngine;
        this.signer = signer;
        this.router = router;
        this.cache = cache;
        this.embedder = embedder;
        this.cacheProps = cacheProps;
        this.rateLimiter = rateLimiter;
        this.budgetGuard = budgetGuard;
        this.requestLimits = requestLimits;
        this.circuitBreaker = circuitBreaker;
        this.costTable = costTable;
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
        String user = caller.subject();
        String clearance = caller.clearance().label();

        // LLM10 resource controls (ADR-0038), cheapest checks first.
        if (!rateLimiter.tryAcquire(user)) {
            throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, "rate limit exceeded");
        }
        requestLimits.validateInputSize(request.query());
        int inputTokens = RequestLimits.estimateTokens(request.query());
        // Pre-check uses a conservative tier1 estimate over worst-case output (routing happens below).
        double estimatedCost = costTable.costUnits(ModelTier.TIER1_SMALL, inputTokens, requestLimits.maxOutputTokens());
        if (budgetGuard.wouldExceed(user, estimatedCost)) {
            throw new ResponseStatusException(HttpStatus.PAYMENT_REQUIRED, "daily budget exceeded");
        }

        // Semantic-cache lookup — within the caller's clearance partition only (ADR-0036).
        float[] queryVec = null;
        if (cacheProps.enabled()) {
            queryVec = embedder.embed(request.query());
            Optional<SemanticCache.CacheHit> hit = cache.lookup(clearance, cacheProps.corpusVersion(), queryVec);
            if (hit.isPresent()) {
                log.info("Semantic-cache HIT for '{}' at '{}' (sim={})", user, clearance, hit.get().similarity());
                return ResponseEntity.ok(fromCache(hit.get()));
            }
        }

        // Miss → route + proxy to rag-engine (wrapped in the circuit breaker + read timeout).
        ModelRouter.RoutingDecision decision = router.route(request.query(), http.getHeader(ModelRouter.QUALITY_HEADER));
        String assertion = signer.sign(user, caller.clearance());
        log.info("Cache miss → proxying for '{}' at '{}' via tier '{}' (escalated={})",
                user, clearance, decision.tier().label(), decision.escalated());
        JsonNode answer = circuitBreaker.call(() ->
                ragEngine.query(assertion, decision.tier().label(), requestLimits.maxOutputTokens(), request));

        // Trusted-write + budget post-accounting (actual cost estimated from answer length; task 8 swaps
        // in real token usage surfaced from rag-engine).
        if (cacheProps.enabled() && answer != null) {
            cache.put(clearance, cacheProps.corpusVersion(), queryVec,
                    new SemanticCache.CachedAnswer(answer.toString(), decision.model()));
        }
        int completionTokens = RequestLimits.estimateTokens(answerText(answer));
        budgetGuard.record(user, costTable.costUnits(decision.tier(), inputTokens, completionTokens));

        return ResponseEntity.ok(withSections(answer, decision.tier().label(), decision.model(),
                decision.escalated(), false, 0.0));
    }

    private static String answerText(JsonNode body) {
        return body != null && body.hasNonNull("answer") ? body.get("answer").asText() : "";
    }

    /** Build the response from a cache hit: parse the stored answer + add cache/routing sections. */
    private JsonNode fromCache(SemanticCache.CacheHit hit) {
        JsonNode body;
        try {
            body = mapper.readTree(hit.answerJson());
        } catch (Exception e) {
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
