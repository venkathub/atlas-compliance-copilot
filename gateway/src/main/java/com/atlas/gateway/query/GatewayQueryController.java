package com.atlas.gateway.query;

import com.atlas.gateway.auth.CallerClearance;
import com.atlas.gateway.auth.DownstreamClearanceSigner;
import com.atlas.gateway.cache.CacheProperties;
import com.atlas.gateway.cache.QueryEmbedder;
import com.atlas.gateway.cache.SemanticCache;
import com.atlas.gateway.metering.CostMeter;
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
import java.time.Duration;
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
 * pre-check (402) → input-size cap (413) → PII ingress redaction (LLM02) → semantic-cache lookup within the
 * caller's clearance partition (ADR-0036; hit ⇒ return at ~zero cost) → cost-aware routing (ADR-0035) →
 * downstream call wrapped in the circuit breaker + timeout (ADR-0039; 503 fallback) → PII egress redaction +
 * output sanitization (ADR-0037, LLM02/LLM05) → trusted-write + budget post-accounting (real tokens) →
 * metering (ADR-0040). The response carries the full §2.3 envelope (routing/cache/redaction/cost).
 */
@RestController
@RequestMapping("/v1")
public class GatewayQueryController {

    private static final Logger log = LoggerFactory.getLogger(GatewayQueryController.class);
    private static final String ROUTE = "/v1/query";

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
    private final CostMeter meter;
    private final ObjectMapper mapper;

    public GatewayQueryController(RagEngineClient ragEngine, DownstreamClearanceSigner signer,
            ModelRouter router, SemanticCache cache, QueryEmbedder embedder, CacheProperties cacheProps,
            RateLimiter rateLimiter, BudgetGuard budgetGuard, RequestLimits requestLimits,
            ModelCircuitBreaker circuitBreaker, CostTable costTable, PiiRedactor piiRedactor,
            OutputSanitizer sanitizer, SafetyProperties safety, CostMeter meter, ObjectMapper mapper) {
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
        this.meter = meter;
        this.mapper = mapper;
    }

    @PostMapping("/query")
    public ResponseEntity<JsonNode> query(@RequestBody(required = false) GatewayQueryRequest request,
            HttpServletRequest http) {
        long startNanos = System.nanoTime();
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
            meter.recordRateLimitRejected();
            throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, "rate limit exceeded");
        }
        requestLimits.validateInputSize(request.query());
        int inputTokens = RequestLimits.estimateTokens(request.query());
        double estimatedCost = costTable.costUnits(ModelTier.TIER1_SMALL, inputTokens, requestLimits.maxOutputTokens());
        if (budgetGuard.wouldExceed(user, estimatedCost)) {
            meter.recordBudgetRejected();
            throw new ResponseStatusException(HttpStatus.PAYMENT_REQUIRED, "daily budget exceeded");
        }

        // PII ingress redaction (LLM02): scrub the prompt before embedding / rag-engine.
        GatewayQueryRequest safeRequest = redactIngress(request);

        // Semantic-cache lookup — within the caller's clearance partition only (ADR-0036).
        float[] queryVec = null;
        if (cacheProps.enabled()) {
            queryVec = embedder.embed(safeRequest.query());
            Optional<SemanticCache.CacheHit> hit = cache.lookup(clearance, cacheProps.corpusVersion(), queryVec);
            if (hit.isPresent()) {
                meter.recordCacheHit();
                log.info("Semantic-cache HIT for '{}' at '{}' (sim={})", user, clearance, hit.get().similarity());
                JsonNode cached = fromCache(hit.get(), startNanos);
                meter.recordRequest(ROUTE, "cache", true, elapsed(startNanos));
                return ResponseEntity.ok(cached);
            }
            meter.recordCacheMiss();
        }

        // Miss → route + proxy to rag-engine (wrapped in the circuit breaker + read timeout).
        ModelRouter.RoutingDecision decision = router.route(safeRequest.query(),
                http.getHeader(ModelRouter.QUALITY_HEADER), http.getHeader(ModelRouter.FT_HINT_HEADER));
        String tier = decision.tier().label();
        String assertion = signer.sign(user, caller.clearance());
        log.info("Cache miss → proxying for '{}' at '{}' via tier '{}' (escalated={})",
                user, clearance, tier, decision.escalated());
        JsonNode answer = circuitBreaker.call(() ->
                ragEngine.query(assertion, tier, requestLimits.maxOutputTokens(), safeRequest));

        // Trusted-write the RAW answer (egress redaction is applied per-read, below).
        if (cacheProps.enabled() && answer != null) {
            cache.put(clearance, cacheProps.corpusVersion(), queryVec,
                    new SemanticCache.CachedAnswer(answer.toString(), decision.model()));
        }

        // Real token usage (ADR-0040) → cost + budget accounting; fall back to an estimate if absent.
        int[] tokens = tokens(answer, inputTokens);
        double costUnits = costTable.costUnits(decision.tier(), tokens[0], tokens[1]);
        budgetGuard.record(user, costUnits);
        meter.recordCost(ROUTE, tier, user, costUnits);

        Map<String, Integer> redactionCounts = applyEgressSafety(answer);
        redactionCounts.forEach(meter::recordRedaction);

        long latencyMs = elapsed(startNanos).toMillis();
        meter.recordRequest(ROUTE, tier, false, elapsed(startNanos));
        JsonNode body = withSections(answer, new Meta(tier, decision.model(), decision.escalated(),
                false, 0.0, redactionCounts, tokens[0], tokens[1], costUnits, latencyMs));
        return ResponseEntity.ok(body);
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

    /** Real token usage from rag-engine's response, or a deterministic estimate when absent. */
    private static int[] tokens(JsonNode answer, int inputTokensEstimate) {
        JsonNode usage = answer == null ? null : answer.get("usage");
        if (usage != null) {
            int pt = usage.path("promptTokens").asInt(0);
            int ct = usage.path("completionTokens").asInt(0);
            if (pt > 0 || ct > 0) {
                return new int[] {pt, ct};
            }
        }
        return new int[] {inputTokensEstimate, RequestLimits.estimateTokens(answerText(answer))};
    }

    private static String answerText(JsonNode body) {
        return body != null && body.hasNonNull("answer") ? body.get("answer").asText() : "";
    }

    private static Duration elapsed(long startNanos) {
        return Duration.ofNanos(System.nanoTime() - startNanos);
    }

    /** Build the response from a cache hit: parse the stored RAW answer, apply egress safety, add sections. */
    private JsonNode fromCache(SemanticCache.CacheHit hit, long startNanos) {
        JsonNode body;
        try {
            body = mapper.readTree(hit.answerJson());
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "cache decode error");
        }
        Map<String, Integer> counts = applyEgressSafety(body);
        counts.forEach(meter::recordRedaction);
        // A cache hit incurs no model call → ~zero serving cost.
        return withSections(body, new Meta("cache", hit.model(), false, true, hit.similarity(),
                counts, 0, 0, 0.0, elapsed(startNanos).toMillis()));
    }

    /**
     * PII egress redaction (LLM02) + output sanitization (LLM05) on the answer + citation snippets. Mutates
     * {@code body} in place; returns per-type counts (no PII).
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

    /** Carrier for the §2.3 envelope sections merged onto the relayed/cached response. */
    private record Meta(String modelTier, String model, boolean escalated, boolean cacheHit, double similarity,
            Map<String, Integer> redactionCounts, int promptTokens, int completionTokens, double costUnits,
            long latencyMs) {
    }

    /** Merge the §2.3 {@code routing} + {@code cache} + {@code redaction} + {@code cost} sections. */
    private JsonNode withSections(JsonNode body, Meta m) {
        if (body instanceof ObjectNode node) {
            ObjectNode routing = node.objectNode();
            routing.put("modelTier", m.modelTier());
            routing.put("model", m.model());
            routing.put("escalated", m.escalated());
            node.set("routing", routing);

            ObjectNode cacheNode = node.objectNode();
            cacheNode.put("hit", m.cacheHit());
            if (m.cacheHit()) {
                cacheNode.put("similarity", m.similarity());
            }
            node.set("cache", cacheNode);

            ObjectNode redaction = node.objectNode();
            redaction.put("applied", !m.redactionCounts().isEmpty());
            ObjectNode countsNode = redaction.objectNode();
            m.redactionCounts().forEach(countsNode::put);
            redaction.set("counts", countsNode);
            node.set("redaction", redaction);

            ObjectNode cost = node.objectNode();
            cost.put("promptTokens", m.promptTokens());
            cost.put("completionTokens", m.completionTokens());
            cost.put("costUnits", m.costUnits());
            cost.put("latencyMs", m.latencyMs());
            node.set("cost", cost);
        }
        return body;
    }
}
