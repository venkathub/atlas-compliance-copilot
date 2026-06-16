package com.atlas.gateway.query;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.atlas.gateway.auth.CallerClearance;
import com.atlas.gateway.auth.Clearance;
import com.atlas.gateway.auth.DownstreamClearanceSigner;
import com.atlas.gateway.auth.GatewayProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

/** Web-layer test for the pass-through query controller (standalone MockMvc, mocked downstream). */
class GatewayQueryControllerTest {

    private final RagEngineClient ragEngine = Mockito.mock(RagEngineClient.class);
    private final DownstreamClearanceSigner signer =
            new DownstreamClearanceSigner(new GatewayProperties("http://localhost:8081", "test-internal-secret"));
    private final ObjectMapper json = new ObjectMapper();
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.standaloneSetup(new GatewayQueryController(ragEngine, signer)).build();
    }

    @Test
    void proxiesWithSignedAssertionAndRelaysAnswer() throws Exception {
        when(ragEngine.query(
                // a non-blank assertion that decodes to the caller's clearance is signed and passed through
                argThat(a -> a != null && !a.isBlank()), any(GatewayQueryRequest.class)))
                .thenReturn(json.readTree("{\"answer\":\"Open exceptions [1].\",\"citations\":[]}"));

        mvc.perform(post("/v1/query")
                        .requestAttr(CallerClearance.ATTRIBUTE, new CallerClearance("priya", Clearance.COMPLIANCE))
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\",\"topK\":6}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.answer").value("Open exceptions [1]."));
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
        // No CallerClearance attribute (would be set by JwtClearanceFilter on the real path).
        mvc.perform(post("/v1/query")
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\"}"))
                .andExpect(status().isUnauthorized());
    }
}
