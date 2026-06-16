package com.atlas.gateway.query;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.atlas.gateway.auth.CallerClearance;
import com.atlas.gateway.auth.Clearance;
import com.atlas.gateway.auth.DownstreamClearanceSigner;
import com.atlas.gateway.auth.GatewayProperties;
import com.atlas.gateway.router.ModelRouter;
import com.atlas.gateway.router.RoutingProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

/** Web-layer test for the query controller (standalone MockMvc, mocked downstream, real router/signer). */
class GatewayQueryControllerTest {

    private final RagEngineClient ragEngine = Mockito.mock(RagEngineClient.class);
    private final DownstreamClearanceSigner signer =
            new DownstreamClearanceSigner(new GatewayProperties("http://localhost:8081", "test-internal-secret"));
    private final ModelRouter router = new ModelRouter(
            new RoutingProperties("tier1-small", "qwen2.5:3b-instruct", "qwen2.5:7b-instruct", 1200, true, false, null));
    private final ObjectMapper json = new ObjectMapper();
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.standaloneSetup(new GatewayQueryController(ragEngine, signer, router)).build();
    }

    @Test
    void shortQueryRoutesToTier1AndRelaysAnswerWithRoutingSection() throws Exception {
        when(ragEngine.query(argThat(a -> a != null && !a.isBlank()), eq("tier1-small"), any(GatewayQueryRequest.class)))
                .thenReturn(json.readTree("{\"answer\":\"Open exceptions [1].\",\"citations\":[]}"));

        mvc.perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\",\"topK\":6}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.answer").value("Open exceptions [1]."))
                .andExpect(jsonPath("$.routing.modelTier").value("tier1-small"))
                .andExpect(jsonPath("$.routing.model").value("qwen2.5:3b-instruct"))
                .andExpect(jsonPath("$.routing.escalated").value(false));
    }

    @Test
    void qualityHighHeaderEscalatesToTier2() throws Exception {
        when(ragEngine.query(argThat(a -> a != null && !a.isBlank()), eq("tier2-mid"), any(GatewayQueryRequest.class)))
                .thenReturn(json.readTree("{\"answer\":\"Detailed [1].\",\"citations\":[]}"));

        mvc.perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .header(ModelRouter.QUALITY_HEADER, "high")
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\",\"topK\":6}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.routing.modelTier").value("tier2-mid"))
                .andExpect(jsonPath("$.routing.escalated").value(true));
    }

    @Test
    void rejectsBlankQuery() throws Exception {
        mvc.perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json")
                        .content("{\"query\":\"  \"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void unauthorizedWhenNoVerifiedClearance() throws Exception {
        mvc.perform(post("/v1/query")
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\"}"))
                .andExpect(status().isUnauthorized());
    }
}
