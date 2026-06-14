package com.atlas.ragengine.qa;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.guardrail.GuardrailProperties;
import com.atlas.ragengine.guardrail.InjectionGuardrail;
import com.atlas.ragengine.observability.QueryTracer;
import com.atlas.ragengine.observability.RecordingObservationHandler;
import com.atlas.ragengine.observability.RedactionFilter;
import com.atlas.ragengine.observability.TracingProperties;
import com.atlas.ragengine.retrieval.HybridDocumentRetriever.RetrievalResult;
import com.atlas.ragengine.retrieval.HybridDocumentRetriever.RetrievalStats;
import com.atlas.ragengine.retrieval.HybridRetriever;
import com.atlas.ragengine.retrieval.RetrievedChunk;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.RbacFilterBuilder;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import io.micrometer.observation.ObservationRegistry;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

/**
 * Offline tracing IT (D-P2 §4.2): asserts the {@code gen_ai.*} span tree + request/clearance
 * attributes via an in-memory observation recorder, the required operation-duration metric, and the
 * compliance-critical redaction default (no chunk text / PII in traces unless content=full).
 */
class QueryServiceTracingTest {

    private final InjectionGuardrail guardrail = new InjectionGuardrail(GuardrailProperties.defaults());
    private final CitationExtractor citations = new CitationExtractor(new RbacFilterBuilder());

    private RecordingObservationHandler handler;
    private SimpleMeterRegistry meters;

    private QueryService service(List<RetrievedChunk> chunks, StubChatModel chat, TracingProperties props) {
        ObservationRegistry registry = ObservationRegistry.create();
        handler = new RecordingObservationHandler();
        registry.observationConfig().observationHandler(handler);
        meters = new SimpleMeterRegistry();
        QueryTracer tracer = new QueryTracer(registry, meters, props, new RedactionFilter(props.getPiiDenylist()));
        return new QueryService(fixedRetriever(chunks), guardrail, citations, chat, tracer);
    }

    @Test
    void emitsSpanTreeWithRequestAndClearanceAttributesAndDurationMetric() {
        QueryService svc = service(List.of(src("public", "doc-a")),
                new StubChatModel("grounded in [1]"), TracingProperties.defaults());

        svc.answer("revenue?", ClearanceLevel.COMPLIANCE, 6, "req-123");

        var root = handler.byName("atlas.query");
        assertThat(root).isNotNull();
        assertThat(root.value("atlas.request_id")).isEqualTo("req-123");
        assertThat(root.value("atlas.clearance")).isEqualTo("compliance");
        assertThat(root.value("atlas.top_k")).isEqualTo("6");

        assertThat(handler.byName("retrieve")).isNotNull();
        assertThat(handler.byName("retrieve").value("retrieve.reranked")).isEqualTo("1");
        assertThat(handler.byName("guardrail.scan").value("guardrail.safe")).isEqualTo("1");

        assertThat(meters.find("gen_ai.client.operation.duration").timer()).isNotNull();
        assertThat(meters.find("gen_ai.client.operation.duration").timer().count()).isEqualTo(1L);
    }

    @Test
    void contentOffByDefaultLeaksNoChunkTextOrPii() {
        // chunk content + an SSN-bearing answer must NOT appear in any span attribute.
        QueryService svc = service(List.of(src("public", "doc-a")),
                new StubChatModel("answer mentioning 900-12-3456 [1]"), TracingProperties.defaults());

        svc.answer("q", ClearanceLevel.PUBLIC, 6, "r");

        assertThat(handler.recorded).noneMatch(r -> r.anyValueContains("content for doc-a"));
        assertThat(handler.recorded).noneMatch(r -> r.anyValueContains("900-12-3456"));
        assertThat(handler.byName("atlas.query").value("gen_ai.completion")).isNull();
    }

    @Test
    void contentFullCapturesRedactedPromptAndCompletion() {
        TracingProperties full = new TracingProperties();
        full.setContent("full");
        full.setPiiDenylist(List.of("Marcus T. Vale"));
        QueryService svc = service(List.of(src("public", "doc-a")),
                new StubChatModel("Per Marcus T. Vale, SSN 900-12-3456 [1]"), full);

        svc.answer("q", ClearanceLevel.PUBLIC, 6, "r");

        String completion = handler.byName("atlas.query").value("gen_ai.completion");
        assertThat(completion).isNotNull()
                .contains(RedactionFilter.MASK)
                .doesNotContain("900-12-3456")
                .doesNotContain("Marcus T. Vale");
        assertThat(handler.byName("atlas.query").value("gen_ai.prompt")).isNotNull();
    }

    private static HybridRetriever fixedRetriever(List<RetrievedChunk> chunks) {
        RetrievalStats stats = new RetrievalStats(chunks.size(), 0, chunks.size(), chunks.size(), "compliance");
        RetrievalResult result = new RetrievalResult(chunks, stats);
        return (query, caller, topK) -> result;
    }

    private static RetrievedChunk src(String clearance, String docId) {
        return new RetrievedChunk(UUID.randomUUID(), UUID.randomUUID(),
                "content for " + docId, clearance,
                Map.of("docId", docId, "title", "Title " + docId, "sourceUri", "atlas://" + docId), 0.5);
    }
}
