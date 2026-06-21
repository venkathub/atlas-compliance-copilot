package com.atlas.gateway.auth;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

/** Web-layer contract test for {@code POST /v1/auth/resource-token} (standalone MockMvc), ADR-0046. */
class ResourceTokenControllerTest {

    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        IdpProperties idp = new IdpProperties("test-signing-key", "atlas-sim-idp", 3600, null);
        ResourceTokenProperties resource = new ResourceTokenProperties("atlas-mcp-tools", 300);
        ResourceScopedTokenIssuer issuer = new ResourceScopedTokenIssuer(idp, resource);
        DevUserDirectory directory = new DevUserDirectory(idp.devUsers());
        mvc = MockMvcBuilders.standaloneSetup(new ResourceTokenController(issuer, directory)).build();
    }

    @Test
    void mintsAudienceScopedTokenForKnownUser() throws Exception {
        mvc.perform(post("/v1/auth/resource-token")
                        .contentType("application/json")
                        .content("{\"user\":\"priya\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token").isNotEmpty())
                .andExpect(jsonPath("$.tokenType").value("Bearer"))
                .andExpect(jsonPath("$.subject").value("priya"))
                .andExpect(jsonPath("$.clearance").value("compliance"))
                .andExpect(jsonPath("$.audience").value("atlas-mcp-tools"))
                .andExpect(jsonPath("$.expiresIn").isNumber());
    }

    @Test
    void rejectsUnknownUser() throws Exception {
        mvc.perform(post("/v1/auth/resource-token")
                        .contentType("application/json")
                        .content("{\"user\":\"mallory\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void rejectsMissingUser() throws Exception {
        mvc.perform(post("/v1/auth/resource-token")
                        .contentType("application/json")
                        .content("{}"))
                .andExpect(status().isBadRequest());
    }
}
