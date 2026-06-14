package com.atlas.ragengine.observability;

import io.micrometer.common.KeyValue;
import io.micrometer.core.instrument.DistributionSummary;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationRegistry;
import java.time.Duration;
import java.util.List;
import java.util.function.Function;
import java.util.function.Supplier;
import org.springframework.ai.chat.metadata.ChatResponseMetadata;
import org.springframework.ai.chat.metadata.Usage;

/**
 * Emits OTel {@code gen_ai.*}-aligned spans + the required {@code gen_ai.client.operation.duration}
 * metric for the QA pipeline (ADR-0030, E2). Spans nest under a root {@code atlas.query} span carrying
 * {@code atlas.request_id}/{@code atlas.clearance} so a trace links back to its request. Spring AI's own
 * {@code gen_ai.embeddings}/{@code gen_ai.chat} model spans nest automatically when present.
 *
 * <p>Content capture is redaction-gated (D-P2-10): prompt/response text is attached only when
 * {@link TracingProperties} mode is {@code FULL}, and always passes through {@link RedactionFilter}.
 */
public class QueryTracer {

    static final String OP_DURATION_METRIC = "gen_ai.client.operation.duration";
    static final String TOKEN_USAGE_METRIC = "gen_ai.client.token.usage";
    static final String GEN_AI_SYSTEM = "ollama";

    private final ObservationRegistry observations;
    private final MeterRegistry meters;
    private final TracingProperties props;
    private final RedactionFilter redaction;

    public QueryTracer(ObservationRegistry observations, MeterRegistry meters,
            TracingProperties props, RedactionFilter redaction) {
        this.observations = observations;
        this.meters = meters;
        this.props = props;
        this.redaction = redaction;
    }

    /** No-op tracer for unit tests / back-compat construction (records nothing, never null). */
    public static QueryTracer noop() {
        return new QueryTracer(ObservationRegistry.NOOP, new SimpleMeterRegistry(),
                TracingProperties.defaults(), RedactionFilter.defaults());
    }

    /** Start (but don't stop) the root span for one query. Caller stops it in a finally. */
    public Observation startQuery(String requestId, String clearance, int topK) {
        return Observation.createNotStarted("atlas.query", observations)
                .contextualName("atlas query")
                .lowCardinalityKeyValue("atlas.clearance", clearance)
                .lowCardinalityKeyValue("atlas.top_k", Integer.toString(topK))
                .highCardinalityKeyValue("atlas.request_id", requestId)
                .start();
    }

    /**
     * Run {@code work} as a child span of {@code parent}; attributes are derived from the result so
     * they reflect what actually happened (e.g. retrieval counts) and are recorded before stop.
     */
    public <T> T span(Observation parent, String name, Supplier<T> work,
            Function<T, List<KeyValue>> attrs) {
        Observation obs = Observation.createNotStarted(name, observations)
                .parentObservation(parent)
                .start();
        T result = null;
        try (Observation.Scope scope = obs.openScope()) {
            result = work.get();
            return result;
        } catch (RuntimeException e) {
            obs.error(e);
            throw e;
        } finally {
            if (result != null && attrs != null) {
                attrs.apply(result).forEach(obs::lowCardinalityKeyValue);
            }
            obs.stop();
        }
    }

    /** Record the OTel-required operation-duration + token-usage metrics for a model call. */
    public void recordModelCall(String operation, String model, Duration duration,
            ChatResponseMetadata metadata) {
        String modelTag = (model == null || model.isBlank()) ? "unknown" : model;
        Timer.builder(OP_DURATION_METRIC)
                .tag("gen_ai.operation.name", operation)
                .tag("gen_ai.request.model", modelTag)
                .tag("gen_ai.system", GEN_AI_SYSTEM)
                .register(meters)
                .record(duration);
        Usage usage = metadata == null ? null : metadata.getUsage();
        if (usage != null) {
            recordTokens(modelTag, "input", usage.getPromptTokens());
            recordTokens(modelTag, "output", usage.getCompletionTokens());
        }
    }

    private void recordTokens(String model, String type, Integer tokens) {
        if (tokens == null) {
            return;
        }
        DistributionSummary.builder(TOKEN_USAGE_METRIC)
                .tag("gen_ai.token.type", type)
                .tag("gen_ai.request.model", model)
                .tag("gen_ai.system", GEN_AI_SYSTEM)
                .register(meters)
                .record(tokens);
    }

    /** True when redaction-gated content capture is enabled (dev-only, D-P2-10). */
    public boolean contentEnabled() {
        return props.mode() == ContentMode.FULL;
    }

    /**
     * Attach redacted content to a span as a high-cardinality attribute — ONLY when content capture is
     * on. A no-op (and nothing reaches the trace) by default, honouring RBAC/PII in the trace plane.
     */
    public void recordContent(Observation observation, String key, String content) {
        if (!contentEnabled() || observation == null || content == null) {
            return;
        }
        observation.highCardinalityKeyValue(key, redaction.redact(content));
    }
}
