package com.atlas.ragengine.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.atlas.ragengine.qa.Citation;
import com.atlas.ragengine.qa.QueryService;
import com.atlas.ragengine.qa.QueryService.QaResult;
import com.atlas.ragengine.retrieval.HybridDocumentRetriever.RetrievalStats;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.ClearanceResolver;
import com.atlas.ragengine.security.RequestHeaders;
import java.util.List;
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
        when(queryService.answer(eq("aml?"), eq(ClearanceLevel.COMPLIANCE), anyInt())).thenReturn(result);

        mvc.perform(post("/v1/query")
                        .header("X-Atlas-User", "priya")
                        .contentType("application/json")
                        .content("{\"query\":\"aml?\",\"topK\":6}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.answer").value("Open exceptions [1]."))
                .andExpect(jsonPath("$.citations[0].marker").value(1))
                .andExpect(jsonPath("$.citations[0].clearance").value("compliance"))
                .andExpect(jsonPath("$.retrieval.clearanceApplied").value("compliance"))
                .andExpect(jsonPath("$.retrieval.reranked").value(6));
    }

    @Test
    void rejectsBlankQuery() throws Exception {
        when(resolver.resolve(any(RequestHeaders.class))).thenReturn(ClearanceLevel.PUBLIC);
        mvc.perform(post("/v1/query").contentType("application/json").content("{\"query\":\"  \"}"))
                .andExpect(status().isBadRequest());
    }
}
