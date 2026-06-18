package com.atlas.gateway.config;

import com.atlas.gateway.metering.CostMeter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Wires the gateway cost/token/latency metering (ADR-0040, G-P3-7) over the Boot-autoconfigured
 * {@link MeterRegistry} (exported to Prometheus at {@code /actuator/prometheus}).
 *
 * <p>Circuit-breaker state is surfaced best-effort via Resilience4j's own {@code resilience4j_circuitbreaker_state}
 * Micrometer metric when its binder is on the classpath; the dashboard panel degrades gracefully otherwise.
 */
@Configuration
public class MeteringConfig {

    @Bean
    CostMeter costMeter(MeterRegistry registry) {
        return new CostMeter(registry);
    }
}
