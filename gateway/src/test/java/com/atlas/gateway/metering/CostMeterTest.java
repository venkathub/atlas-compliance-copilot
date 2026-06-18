package com.atlas.gateway.metering;

import static org.assertj.core.api.Assertions.assertThat;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Duration;
import org.junit.jupiter.api.Test;

class CostMeterTest {

    private final SimpleMeterRegistry registry = new SimpleMeterRegistry();
    private final CostMeter meter = new CostMeter(registry);

    @Test
    void recordsCostUnitsWithTags() {
        meter.recordCost("/v1/query", "tier1-small", "priya", 0.42);
        var counter = registry.find("atlas.gateway.cost.units")
                .tag("tier", "tier1-small").tag("user", "priya").counter();
        assertThat(counter).isNotNull();
        assertThat(counter.count()).isEqualTo(0.42);
    }

    @Test
    void recordsRequestDurationWithCacheHitTag() {
        meter.recordRequest("/v1/query", "cache", true, Duration.ofMillis(12));
        var timer = registry.find("atlas.gateway.request.duration").tag("cache_hit", "true").timer();
        assertThat(timer).isNotNull();
        assertThat(timer.count()).isEqualTo(1);
    }

    @Test
    void recordsCacheRejectionAndRedactionMeters() {
        meter.recordCacheHit();
        meter.recordCacheMiss();
        meter.recordRateLimitRejected();
        meter.recordBudgetRejected();
        meter.recordRedaction("SSN_TIN", 2);

        assertThat(registry.find("atlas.gateway.cache.hit").counter().count()).isEqualTo(1);
        assertThat(registry.find("atlas.gateway.cache.miss").counter().count()).isEqualTo(1);
        assertThat(registry.find("atlas.gateway.ratelimit.rejected").counter().count()).isEqualTo(1);
        assertThat(registry.find("atlas.gateway.budget.rejected").counter().count()).isEqualTo(1);
        assertThat(registry.find("atlas.gateway.redaction.count").tag("entity_type", "SSN_TIN").counter().count())
                .isEqualTo(2);
    }

    @Test
    void zeroCostIsNotRecorded() {
        meter.recordCost("/v1/query", "cache", "priya", 0.0);
        assertThat(registry.find("atlas.gateway.cost.units").counter()).isNull();
    }
}
