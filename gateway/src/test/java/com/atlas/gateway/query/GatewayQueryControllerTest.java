package com.atlas.gateway.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
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
import com.atlas.gateway.router.ModelRouter;
import com.atlas.gateway.router.RoutingProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

/** Web-layer test for the query controller (standalone MockMvc; mocked downstream, real router/signer). */
class GatewayQueryControllerTest {

    private final RagEngineClient ragEngine = Mockito.mock(RagEngineClient.class);
    private final DownstreamClearanceSigner signer =
            new DownstreamClearanceSigner(new GatewayProperties("http://localhost:8081", "test-internal-secret"));
    private final ModelRouter router = new ModelRouter(
            new RoutingProperties("tier1-small", "qwen2.5:3b-instruct", "qwen2.5:7b-instruct", 1200, true, false, null));
    private final ObjectMapper json = new ObjectMapper();
    private final QueryEmbedder stubEmbedder = text -> new float[] {1f, 0f, 0f};

    private MockMvc mvcWith(SemanticCache cache, boolean cacheEnabled) {
        CacheProperties props = new CacheProperties(cacheEnabled, 0.95, 86400, "v1", false);
        return MockMvcBuilders.standaloneSetup(
                new GatewayQueryController(ragEngine, signer, router, cache, stubEmbedder, props, json)).build();
    }

    @Test
    void shortQueryRoutesToTier1AndRelaysAnswerWithSections() throws Exception {
        when(ragEngine.query(argThat(a -> a != null && !a.isBlank()), eq("tier1-small"), any(GatewayQueryRequest.class)))
                .thenReturn(json.readTree("{\"answer\":\"Open exceptions [1].\",\"citations\":[]}"));

        mvcWith(new NoOpSemanticCache(), false).perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\",\"topK\":6}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.answer").value("Open exceptions [1]."))
                .andExpect(jsonPath("$.routing.modelTier").value("tier1-small"))
                .andExpect(jsonPath("$.cache.hit").value(false));
    }

    @Test
    void qualityHighHeaderEscalatesToTier2() throws Exception {
        when(ragEngine.query(argThat(a -> a != null && !a.isBlank()), eq("tier2-mid"), any(GatewayQueryRequest.class)))
                .thenReturn(json.readTree("{\"answer\":\"Detailed [1].\",\"citations\":[]}"));

        mvcWith(new NoOpSemanticCache(), false).perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .header(ModelRouter.QUALITY_HEADER, "high")
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\",\"topK\":6}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.routing.modelTier").value("tier2-mid"))
                .andExpect(jsonPath("$.routing.escalated").value(true));
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

        mvcWith(hitCache, true).perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\",\"topK\":6}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.answer").value("Cached [1]."))
                .andExpect(jsonPath("$.cache.hit").value(true))
                .andExpect(jsonPath("$.cache.similarity").value(0.97))
                .andExpect(jsonPath("$.routing.modelTier").value("cache"));

        verify(ragEngine, never()).query(anyString(), anyString(), any());
    }

    @Test
    void cacheMissTrustedWritesTheAnswer() throws Exception {
        RecordingCache cache = new RecordingCache();
        when(ragEngine.query(anyString(), eq("tier1-small"), any(GatewayQueryRequest.class)))
                .thenReturn(json.readTree("{\"answer\":\"Fresh [1].\",\"citations\":[]}"));

        mvcWith(cache, true).perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\",\"topK\":6}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.cache.hit").value(false));

        assertThat(cache.puts).isEqualTo(1);
        assertThat(cache.lastClearance).isEqualTo("compliance"); // written into the caller's partition
    }

    @Test
    void rejectsBlankQuery() throws Exception {
        mvcWith(new NoOpSemanticCache(), false).perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json")
                        .content("{\"query\":\"  \"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void unauthorizedWhenNoVerifiedClearance() throws Exception {
        mvcWith(new NoOpSemanticCache(), false).perform(post("/v1/query")
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\"}"))
                .andExpect(status().isUnauthorized());
    }

    /** A cache that always misses but records writes (for the trusted-write assertion). */
    private static final class RecordingCache implements SemanticCache {
        int puts;
        String lastClearance;

        @Override
        public Optional<CacheHit> lookup(String clearance, String corpusVersion, float[] queryVec) {
            return Optional.empty();
        }

        @Override
        public void put(String clearance, String corpusVersion, float[] queryVec, CachedAnswer answer) {
            puts++;
            lastClearance = clearance;
        }
    }
}
