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
import com.atlas.gateway.safety.OutputSanitizer;
import com.atlas.gateway.safety.PiiRedactor;
import com.atlas.gateway.safety.SafetyProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.servlet.http.HttpServletRequest;
import java.util.LinkedHashMap;
import java.util.Map;
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
 * <p>Pipeline: clearance verified by {@code JwtClearanceFilter} (ADR-0034) → rate limit (429) → budget
 * pre-check (402) → input-size cap (413) → <b>PII ingress redaction</b> (LLM02) → semantic-cache lookup
 * within the caller's clearance partition (ADR-0036; hit ⇒ return) → cost-aware routing (ADR-0035) →
 * downstream call wrapped in the circuit breaker + timeout (ADR-0039; 503 fallback) → <b>PII egress
 * redaction + output sanitization</b> (ADR-0037, LLM02/LLM05) → trusted-write + budget post-accounting.
 * Egress safety runs on <b>both</b> the fresh and cache-hit paths (the cache stores the raw answer; the
 * gateway redacts on every read). Full cost metering is task 8.
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
    private final PiiRedactor piiRedactor;
    private final OutputSanitizer sanitizer;
    private final SafetyProperties safety;
    private final ObjectMapper mapper;

    public GatewayQueryController(RagEngineClient ragEngine, DownstreamClearanceSigner signer,
            ModelRouter router, SemanticCache cache, QueryEmbedder embedder, CacheProperties cacheProps,
            RateLimiter rateLimiter, BudgetGuard budgetGuard, RequestLimits requestLimits,
            ModelCircuitBreaker circuitBreaker, CostTable costTable, PiiRedactor piiRedactor,
            OutputSanitizer sanitizer, SafetyProperties safety, ObjectMapper mapper) {
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
        this.piiRedactor = piiRedactor;
        this.sanitizer = sanitizer;
        this.safety = safety;
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
        double estimatedCost = costTable.costUnits(ModelTier.TIER1_SMALL, inputTokens, requestLimits.maxOutputTokens());
        if (budgetGuard.wouldExceed(user, estimatedCost)) {
            throw new ResponseStatusException(HttpStatus.PAYMENT_REQUIRED, "daily budget exceeded");
        }

        // PII ingress redaction (LLM02): scrub the prompt before it reaches embedding / rag-engine.
        GatewayQueryRequest safeRequest = redactIngress(request);

        // Semantic-cache lookup — within the caller's clearance partition only (ADR-0036).
        float[] queryVec = null;
        if (cacheProps.enabled()) {
            queryVec = embedder.embed(safeRequest.query());
            Optional<SemanticCache.CacheHit> hit = cache.lookup(clearance, cacheProps.corpusVersion(), queryVec);
            if (hit.isPresent()) {
                log.info("Semantic-cache HIT for '{}' at '{}' (sim={})", user, clearance, hit.get().similarity());
                return ResponseEntity.ok(fromCache(hit.get()));
            }
        }

        // Miss → route + proxy to rag-engine (wrapped in the circuit breaker + read timeout).
        ModelRouter.RoutingDecision decision = router.route(safeRequest.query(), http.getHeader(ModelRouter.QUALITY_HEADER));
        String assertion = signer.sign(user, caller.clearance());
        log.info("Cache miss → proxying for '{}' at '{}' via tier '{}' (escalated={})",
                user, clearance, decision.tier().label(), decision.escalated());
        JsonNode answer = circuitBreaker.call(() ->
                ragEngine.query(assertion, decision.tier().label(), requestLimits.maxOutputTokens(), safeRequest));

        // Trusted-write the RAW answer (egress redaction is applied per-read, below).
        if (cacheProps.enabled() && answer != null) {
            cache.put(clearance, cacheProps.corpusVersion(), queryVec,
                    new SemanticCache.CachedAnswer(answer.toString(), decision.model()));
        }
        int completionTokens = RequestLimits.estimateTokens(answerText(answer));
        budgetGuard.record(user, costTable.costUnits(decision.tier(), inputTokens, completionTokens));

        Map<String, Integer> redactionCounts = applyEgressSafety(answer);
        return ResponseEntity.ok(withSections(answer, decision.tier().label(), decision.model(),
                decision.escalated(), false, 0.0, redactionCounts));
    }

    private GatewayQueryRequest redactIngress(GatewayQueryRequest request) {
        if (!safety.piiEnabled()) {
            return request;
        }
        PiiRedactor.Redaction r = piiRedactor.redact(request.query());
        if (r.applied()) {
            log.info("PII ingress redaction applied (counts={})", r.counts()); // metadata only, never the PII
            return new GatewayQueryRequest(r.text(), request.topK(), request.includeContexts());
        }
        return request;
    }

    private static String answerText(JsonNode body) {
        return body != null && body.hasNonNull("answer") ? body.get("answer").asText() : "";
    }

    /** Build the response from a cache hit: parse the stored RAW answer, apply egress safety, add sections. */
    private JsonNode fromCache(SemanticCache.CacheHit hit) {
        JsonNode body;
        try {
            body = mapper.readTree(hit.answerJson());
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "cache decode error");
        }
        Map<String, Integer> counts = applyEgressSafety(body);
        return withSections(body, "cache", hit.model(), false, true, hit.similarity(), counts);
    }

    /**
     * PII egress redaction (LLM02) + output sanitization (LLM05) on the answer + citation snippets — the
     * carriers of leaked content. Mutates {@code body} in place; returns per-type counts (no PII).
     */
    private Map<String, Integer> applyEgressSafety(JsonNode body) {
        Map<String, Integer> counts = new LinkedHashMap<>();
        if (!(body instanceof ObjectNode node)) {
            return counts;
        }
        if (node.hasNonNull("answer")) {
            node.put("answer", cleanse(node.get("answer").asText(), counts));
        }
        JsonNode citations = node.get("citations");
        if (citations != null && citations.isArray()) {
            for (JsonNode c : citations) {
                if (c instanceof ObjectNode citation && citation.hasNonNull("snippet")) {
                    citation.put("snippet", cleanse(citation.get("snippet").asText(), counts));
                }
            }
        }
        return counts;
    }

    private String cleanse(String text, Map<String, Integer> counts) {
        String out = text;
        if (safety.piiEnabled()) {
            PiiRedactor.Redaction r = piiRedactor.redact(out);
            out = r.text();
            r.counts().forEach((k, v) -> counts.merge(k, v, Integer::sum));
        }
        if (safety.sanitizeEnabled()) {
            OutputSanitizer.Sanitized s = sanitizer.sanitize(out);
            out = s.text();
            if (s.applied()) {
                counts.merge("UNSAFE_OUTPUT", s.removed(), Integer::sum);
            }
        }
        return out;
    }

    /** Merge the §2.3 {@code routing} + {@code cache} + {@code redaction} sections into the response. */
    private JsonNode withSections(JsonNode body, String modelTier, String model, boolean escalated,
            boolean cacheHit, double similarity, Map<String, Integer> redactionCounts) {
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

            ObjectNode redaction = node.objectNode();
            redaction.put("applied", !redactionCounts.isEmpty());
            ObjectNode countsNode = redaction.objectNode();
            redactionCounts.forEach(countsNode::put);
            redaction.set("counts", countsNode);
            node.set("redaction", redaction);
        }
        return body;
    }
}
