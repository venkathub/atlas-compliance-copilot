package com.atlas.gateway.auth;

import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

/** Web-layer contract test for the simulated IdP {@code POST /v1/auth/token} (standalone MockMvc). */
class SimIdpControllerTest {

    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        IdpProperties props = new IdpProperties("test-signing-key", "atlas-sim-idp", 3600, null);
        ClearanceTokenService tokens = new ClearanceTokenService(props);
        DevUserDirectory directory = new DevUserDirectory(props.devUsers());
        mvc = MockMvcBuilders.standaloneSetup(new SimIdpController(tokens, directory)).build();
    }

    @Test
    void mintsTokenForKnownUserWithCorrectClearance() throws Exception {
        mvc.perform(post("/v1/auth/token")
                        .contentType("application/json")
                        .content("{\"user\":\"priya\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token").isNotEmpty())
                .andExpect(jsonPath("$.tokenType").value("Bearer"))
                .andExpect(jsonPath("$.subject").value("priya"))
                .andExpect(jsonPath("$.clearance").value("compliance"))
                .andExpect(jsonPath("$.expiresIn").isNumber());
    }

    @Test
    void rejectsUnknownUser() throws Exception {
        mvc.perform(post("/v1/auth/token")
                        .contentType("application/json")
                        .content("{\"user\":\"mallory\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void rejectsMissingUser() throws Exception {
        mvc.perform(post("/v1/auth/token")
                        .contentType("application/json")
                        .content("{}"))
                .andExpect(status().isBadRequest());
    }
}
