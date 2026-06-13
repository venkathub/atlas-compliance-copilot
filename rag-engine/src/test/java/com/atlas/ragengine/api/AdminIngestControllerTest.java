package com.atlas.ragengine.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.atlas.ragengine.ingest.IngestionService;
import com.atlas.ragengine.ingest.IngestionService.IngestionReport;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.ClearanceResolver;
import com.atlas.ragengine.security.RequestHeaders;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

/** Guard + contract test for {@code POST /v1/admin/ingest} (standalone MockMvc). */
class AdminIngestControllerTest {

    private final IngestionService ingestionService = Mockito.mock(IngestionService.class);
    private final ClearanceResolver resolver = Mockito.mock(ClearanceResolver.class);
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.standaloneSetup(
                new AdminIngestController(ingestionService, resolver)).build();
    }

    @Test
    void restrictedCallerCanTriggerRebuild() throws Exception {
        when(resolver.resolve(any(RequestHeaders.class))).thenReturn(ClearanceLevel.RESTRICTED);
        when(ingestionService.rebuild()).thenReturn(new IngestionReport(24, 24, 0));

        mvc.perform(post("/v1/admin/ingest").header("X-Atlas-User", "bsa-admin"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.documents").value(24))
                .andExpect(jsonPath("$.chunks").value(24))
                .andExpect(jsonPath("$.rejectedUntrusted").value(0));
    }

    @Test
    void nonAdminCallerIsForbiddenAndNoRebuildRuns() throws Exception {
        when(resolver.resolve(any(RequestHeaders.class))).thenReturn(ClearanceLevel.COMPLIANCE);

        mvc.perform(post("/v1/admin/ingest").header("X-Atlas-User", "priya"))
                .andExpect(status().isForbidden());

        verify(ingestionService, never()).rebuild();
    }
}
