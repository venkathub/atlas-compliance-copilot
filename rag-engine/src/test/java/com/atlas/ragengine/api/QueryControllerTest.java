package com.atlas.ragengine.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.atlas.ragengine.qa.Citation;
import com.atlas.ragengine.qa.QueryService;
import com.atlas.ragengine.qa.QueryService.QaResult;
import com.atlas.ragengine.retrieval.HybridDocumentRetriever.RetrievalStats;
import com.atlas.ragengine.retrieval.RetrievedChunk;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.ClearanceResolver;
import com.atlas.ragengine.security.RequestHeaders;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

/** Web-layer contract test for {@code POST /v1/query} (standalone MockMvc, mocked collaborators). */
class QueryControllerTest {

    private final QueryService queryService = Mockito.mock(QueryService.class);
    private final ClearanceResolver resolver = Mockito.mock(ClearanceResolver.class);
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.standaloneSetup(new QueryController(queryService, resolver)).build();
    }

    @Test
    void resolvesCallerFromHeadersAndReturnsContract() throws Exception {
        when(resolver.resolve(any(RequestHeaders.class))).thenReturn(ClearanceLevel.COMPLIANCE);
        Citation citation = new Citation(1, UUID.randomUUID(), UUID.randomUUID(), "l2-x",
                "Northwind Exceptions", "atlas://x", "compliance", 0.83, "…snippet…");
        QaResult result = new QaResult("Open exceptions [1].", List.of(citation),
                new RetrievalStats(20, 5, 12, 6, "compliance"));
        when(queryService.answer(eq("aml?"), eq(ClearanceLevel.COMPLIANCE), anyInt(), anyString()))
                .thenReturn(result);

        mvc.perform(post("/v1/query")
                        .header("X-Atlas-User", "priya")
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\",\"topK\":6}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.answer").value("Open exceptions [1]."))
                .andExpect(jsonPath("$.citations[0].marker").value(1))
                .andExpect(jsonPath("$.citations[0].clearance").value("compliance"))
                .andExpect(jsonPath("$.retrieval.clearanceApplied").value("compliance"))
                .andExpect(jsonPath("$.retrieval.reranked").value(6))
                .andExpect(jsonPath("$.contexts").doesNotExist()); // omitted unless opted in
    }

    @Test
    void includeContextsReturnsFullRbacFilteredChunkText() throws Exception {
        when(resolver.resolve(any(RequestHeaders.class))).thenReturn(ClearanceLevel.COMPLIANCE);
        RetrievedChunk ctx = new RetrievedChunk(UUID.randomUUID(), UUID.randomUUID(),
                "full context chunk text the model saw", "compliance",
                Map.of("docId", "l2-x", "title", "T", "sourceUri", "atlas://x"), 0.83);
        QaResult result = new QaResult("Open exceptions [1].", List.of(),
                new RetrievalStats(20, 5, 12, 6, "compliance"), List.of(ctx));
        when(queryService.answer(eq("aml?"), eq(ClearanceLevel.COMPLIANCE), anyInt(), anyString()))
                .thenReturn(result);

        mvc.perform(post("/v1/query")
                        .header("X-Atlas-User", "priya")
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\",\"topK\":6,\"includeContexts\":true}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.contexts[0].text").value("full context chunk text the model saw"))
                .andExpect(jsonPath("$.contexts[0].clearance").value("compliance"))
                .andExpect(jsonPath("$.contexts[0].chunkId").exists());
    }

    @Test
    void rejectsBlankQuery() throws Exception {
        when(resolver.resolve(any(RequestHeaders.class))).thenReturn(ClearanceLevel.PUBLIC);
        mvc.perform(post("/v1/query").contentType("application/json").content("{\"query\":\"  \"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void verifiedInternalClearanceWinsOverHeaderShim() throws Exception {
        // The Gateway-fronted path: DownstreamClearanceFilter has stashed a verified clearance. The
        // controller must use it and IGNORE the client X-Atlas-Clearance shim (ADR-0034).
        Citation citation = new Citation(1, UUID.randomUUID(), UUID.randomUUID(), "l2-x",
                "Northwind Exceptions", "atlas://x", "compliance", 0.83, "…snippet…");
        QaResult result = new QaResult("Open exceptions [1].", List.of(citation),
                new RetrievalStats(20, 5, 12, 6, "compliance"));
        when(queryService.answer(eq("aml?"), eq(ClearanceLevel.COMPLIANCE), anyInt(), anyString()))
                .thenReturn(result);

        mvc.perform(post("/v1/query")
                        .requestAttr(DownstreamClearanceFilter.ATTRIBUTE, ClearanceLevel.COMPLIANCE)
                        .header("X-Atlas-Clearance", "restricted") // attacker-supplied shim header — must be ignored
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\",\"topK\":6}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.retrieval.clearanceApplied").value("compliance"));

        // The shim resolver must NOT have been consulted when a verified assertion is present.
        Mockito.verifyNoInteractions(resolver);
    }
}
