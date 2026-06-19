package com.atlas.gateway.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.atlas.gateway.auth.CallerClearance;
import com.atlas.gateway.auth.Clearance;
import com.atlas.gateway.auth.DownstreamClearanceSigner;
import com.atlas.gateway.auth.GatewayProperties;
import com.atlas.gateway.cache.CacheProperties;
import com.atlas.gateway.cache.NoOpSemanticCache;
import com.atlas.gateway.cache.QueryEmbedder;
import com.atlas.gateway.cache.SemanticCache;
import com.atlas.gateway.router.CostProperties;
import com.atlas.gateway.router.CostTable;
import com.atlas.gateway.router.ModelRouter;
import com.atlas.gateway.router.RoutingProperties;
import com.atlas.gateway.resilience.AllowAllRateLimiter;
import com.atlas.gateway.resilience.BudgetGuard;
import com.atlas.gateway.resilience.DownstreamUnavailableException;
import com.atlas.gateway.resilience.ModelCircuitBreaker;
import com.atlas.gateway.resilience.NoOpBudgetGuard;
import com.atlas.gateway.metering.CostMeter;
import com.atlas.gateway.resilience.RateLimiter;
import com.atlas.gateway.resilience.RequestLimits;
import com.atlas.gateway.safety.OutputSanitizer;
import com.atlas.gateway.safety.PiiRedactor;
import com.atlas.gateway.safety.SafetyProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.util.List;
import java.util.Optional;
import java.util.function.Function;
import java.util.function.Supplier;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.cloud.client.circuitbreaker.CircuitBreaker;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

/** Web-layer test for the query controller (standalone MockMvc; mocked downstream + control collaborators). */
class GatewayQueryControllerTest {

    private final RagEngineClient ragEngine = Mockito.mock(RagEngineClient.class);
    private final DownstreamClearanceSigner signer =
            new DownstreamClearanceSigner(new GatewayProperties("http://localhost:8081", "test-internal-secret"));
    private final ModelRouter router = new ModelRouter(
            new RoutingProperties("tier1-small", "qwen2.5:3b-instruct", "qwen2.5:7b-instruct", 1200, true, false, null));
    private final CostTable costTable = new CostTable(new CostProperties(0.30, 0.70, 5.00));
    private final ObjectMapper json = new ObjectMapper();
    private final QueryEmbedder stubEmbedder = text -> new float[] {1f, 0f, 0f};

    /** A pass-through circuit breaker: runs the supplier, routes any exception to the fallback. */
    private static final CircuitBreaker PASSTHROUGH = new CircuitBreaker() {
        @Override
        public <T> T run(Supplier<T> toRun, Function<Throwable, T> fallback) {
            try {
                return toRun.get();
            } catch (Throwable t) {
                return fallback.apply(t);
            }
        }
    };

    private MockMvc mvc(SemanticCache cache, boolean cacheEnabled, RateLimiter rateLimiter, BudgetGuard budget) {
        CacheProperties cacheProps = new CacheProperties(cacheEnabled, 0.95, 86400, "v1", false);
        RequestLimits limits = new RequestLimits(6000, 1024);
        ModelCircuitBreaker cb = new ModelCircuitBreaker(PASSTHROUGH, 10);
        PiiRedactor redactor = new PiiRedactor(List.of());
        OutputSanitizer sanitizer = new OutputSanitizer();
        SafetyProperties safety = new SafetyProperties(true, true, List.of());
        CostMeter meter = new CostMeter(new SimpleMeterRegistry());
        return MockMvcBuilders.standaloneSetup(new GatewayQueryController(
                        ragEngine, signer, router, cache, stubEmbedder, cacheProps,
                        rateLimiter, budget, limits, cb, costTable, redactor, sanitizer, safety, meter, json))
                .setControllerAdvice(new GatewayExceptionHandler())
                .build();
    }

    private MockMvc defaultMvc() {
        return mvc(new NoOpSemanticCache(), false, new AllowAllRateLimiter(), new NoOpBudgetGuard());
    }

    @Test
    void shortQueryRoutesToTier1WithSections() throws Exception {
        when(ragEngine.query(argThat(a -> a != null && !a.isBlank()), eq("tier1-small"), anyInt(), any()))
                .thenReturn(json.readTree("{\"answer\":\"Open exceptions [1].\",\"citations\":[]}"));

        defaultMvc().perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json").content("{\"query\":\"aml?\",\"topK\":6}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.answer").value("Open exceptions [1]."))
                .andExpect(jsonPath("$.routing.modelTier").value("tier1-small"))
                .andExpect(jsonPath("$.cache.hit").value(false));
    }

    @Test
    void cacheHitShortCircuitsRagEngine() throws Exception {
        SemanticCache hitCache = new SemanticCache() {
            @Override
            public Optional<CacheHit> lookup(String clearance, String corpusVersion, float[] queryVec) {
                return Optional.of(new CacheHit("{\"answer\":\"Cached [1].\",\"citations\":[]}", "qwen2.5:3b-instruct", 0.97));
            }
            @Override
            public void put(String clearance, String corpusVersion, float[] queryVec, CachedAnswer answer) {
            }
        };

        mvc(hitCache, true, new AllowAllRateLimiter(), new NoOpBudgetGuard()).perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json").content("{\"query\":\"aml?\",\"topK\":6}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.answer").value("Cached [1]."))
                .andExpect(jsonPath("$.cache.hit").value(true));

        verify(ragEngine, never()).query(anyString(), anyString(), anyInt(), any());
    }

    @Test
    void overRateLimitReturns429() throws Exception {
        RateLimiter denying = key -> false;
        mvc(new NoOpSemanticCache(), false, denying, new NoOpBudgetGuard()).perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json").content("{\"query\":\"aml?\"}"))
                .andExpect(status().isTooManyRequests());
        verify(ragEngine, never()).query(anyString(), anyString(), anyInt(), any());
    }

    @Test
    void overBudgetReturns402() throws Exception {
        BudgetGuard exhausted = new BudgetGuard() {
            @Override public boolean wouldExceed(String user, double estimatedCost) {
                return true;
            }
            @Override public void record(String user, double actualCost) {
            }
        };
        mvc(new NoOpSemanticCache(), false, new AllowAllRateLimiter(), exhausted).perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json").content("{\"query\":\"aml?\"}"))
                .andExpect(status().isPaymentRequired());
        verify(ragEngine, never()).query(anyString(), anyString(), anyInt(), any());
    }

    @Test
    void oversizedQueryReturns413() throws Exception {
        String huge = "x".repeat(40_000); // ~10k tokens > 6000 cap
        defaultMvc().perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json").content(json.writeValueAsString(new GatewayQueryRequest(huge, 6, false))))
                .andExpect(status().isPayloadTooLarge());
        verify(ragEngine, never()).query(anyString(), anyString(), anyInt(), any());
    }

    @Test
    void downstreamFailureReturns503WithRetryAfter() throws Exception {
        when(ragEngine.query(anyString(), anyString(), anyInt(), any()))
                .thenThrow(new RuntimeException("rag-engine down"));

        defaultMvc().perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json").content("{\"query\":\"aml?\"}"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(header().exists("Retry-After"));
    }

    @Test
    void budgetIsRecordedOnSuccess() throws Exception {
        RecordingBudget budget = new RecordingBudget();
        when(ragEngine.query(anyString(), eq("tier1-small"), anyInt(), any()))
                .thenReturn(json.readTree("{\"answer\":\"Fresh [1].\",\"citations\":[]}"));

        mvc(new NoOpSemanticCache(), false, new AllowAllRateLimiter(), budget).perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json").content("{\"query\":\"aml?\"}"))
                .andExpect(status().isOk());
        assertThat(budget.recorded).isGreaterThanOrEqualTo(0.0);
        assertThat(budget.records).isEqualTo(1);
    }

    @Test
    void piiInAnswerIsRedactedAtEgress() throws Exception {
        // rag-engine returns an answer carrying an SSN/TIN; it must never leave the gateway (LLM02).
        when(ragEngine.query(anyString(), eq("tier1-small"), anyInt(), any()))
                .thenReturn(json.readTree("{\"answer\":\"The subject SSN is 900-12-3456.\",\"citations\":[]}"));

        defaultMvc().perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json").content("{\"query\":\"aml?\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.answer").value(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("900-12-3456"))))
                .andExpect(jsonPath("$.answer").value(org.hamcrest.Matchers.containsString("[REDACTED:SSN_TIN]")))
                .andExpect(jsonPath("$.redaction.applied").value(true))
                .andExpect(jsonPath("$.redaction.counts.SSN_TIN").value(1));
    }

    @Test
    void realTokenUsageDrivesTheCostSection() throws Exception {
        when(ragEngine.query(anyString(), eq("tier1-small"), anyInt(), any()))
                .thenReturn(json.readTree("{\"answer\":\"A [1].\",\"citations\":[],"
                        + "\"usage\":{\"promptTokens\":800,\"completionTokens\":200}}"));

        defaultMvc().perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json").content("{\"query\":\"aml?\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.cost.promptTokens").value(800))
                .andExpect(jsonPath("$.cost.completionTokens").value(200))
                // tier1 @0.30/1k over 1000 tokens = 0.30 cost-units.
                .andExpect(jsonPath("$.cost.costUnits").value(0.30))
                .andExpect(jsonPath("$.cost.latencyMs").isNumber());
    }

    @Test
    void rejectsBlankQuery() throws Exception {
        defaultMvc().perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json").content("{\"query\":\"  \"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void unauthorizedWhenNoVerifiedClearance() throws Exception {
        defaultMvc().perform(post("/v1/query")
                        .contentType("application/json").content("{\"query\":\"aml?\"}"))
                .andExpect(status().isUnauthorized());
    }

    private static final class RecordingBudget implements BudgetGuard {
        int records;
        double recorded;
        @Override public boolean wouldExceed(String user, double estimatedCost) {
            return false;
        }
        @Override public void record(String user, double actualCost) {
            records++;
            recorded = actualCost;
        }
    }
}
