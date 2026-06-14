package com.atlas.ragengine.config;

import com.atlas.ragengine.observability.QueryTracer;
import com.atlas.ragengine.observability.RedactionFilter;
import com.atlas.ragengine.observability.TracingProperties;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.observation.ObservationRegistry;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Wires P2 observability (ADR-0030 / D-P2-10): the {@link QueryTracer} that emits {@code gen_ai.*}
 * spans + metrics for the QA pipeline, and the redaction-gated content policy. The OTel span/metric
 * export pipeline (OTLP → Langfuse) is auto-configured by Spring Boot from {@code management.*} props.
 */
@Configuration
@EnableConfigurationProperties(TracingProperties.class)
public class AtlasObservabilityConfig {

    @Bean
    RedactionFilter redactionFilter(TracingProperties props) {
        return new RedactionFilter(props.getPiiDenylist());
    }

    @Bean
    QueryTracer queryTracer(ObservationRegistry observationRegistry, MeterRegistry meterRegistry,
            TracingProperties props, RedactionFilter redactionFilter) {
        return new QueryTracer(observationRegistry, meterRegistry, props, redactionFilter);
    }
}
