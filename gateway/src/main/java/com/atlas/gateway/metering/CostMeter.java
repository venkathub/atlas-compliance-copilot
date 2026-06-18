package com.atlas.gateway.metering;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import java.time.Duration;

/**
 * Gateway cost / token / latency metering (ADR-0040, G-P3-7). Token usage reuses the OTel-standard
 * {@code gen_ai.client.token.usage} convention (emitted on the model hop by rag-engine); <b>cost</b> has no
 * OTel-standard metric, so it is a derived, namespaced {@code atlas.gateway.cost.units} counter. Plus
 * gateway-specific meters for latency, cache hit-rate, rate-limit/budget rejections, and redaction counts —
 * the data behind the Grafana cost dashboard.
 *
 * <p>Note: the {@code user} tag is acceptable-cardinality for this dev/demo (a handful of clearance users);
 * a real multi-tenant deploy would drop or bucket it.
 */
public class CostMeter {

    private final MeterRegistry registry;

    public CostMeter(MeterRegistry registry) {
        this.registry = registry;
    }

    /** Accrue cost-units for a served request (counter, tags route/tier/user). */
    public void recordCost(String route, String tier, String user, double costUnits) {
        if (costUnits <= 0) {
            return;
        }
        Counter.builder("atlas.gateway.cost.units")
                .tag("route", route).tag("tier", tier).tag("user", user)
                .description("Derived cost-units served (ADR-0040 cost-units table).")
                .register(registry)
                .increment(costUnits);
    }

    /** Record end-to-end request latency (timer, tags route/tier/cache_hit). */
    public void recordRequest(String route, String tier, boolean cacheHit, Duration latency) {
        Timer.builder("atlas.gateway.request.duration")
                .tag("route", route).tag("tier", tier).tag("cache_hit", Boolean.toString(cacheHit))
                .register(registry)
                .record(latency);
    }

    public void recordCacheHit() {
        registry.counter("atlas.gateway.cache.hit").increment();
    }

    public void recordCacheMiss() {
        registry.counter("atlas.gateway.cache.miss").increment();
    }

    public void recordRateLimitRejected() {
        registry.counter("atlas.gateway.ratelimit.rejected").increment();
    }

    public void recordBudgetRejected() {
        registry.counter("atlas.gateway.budget.rejected").increment();
    }

    /** Count redaction events by entity type (metadata only — never the PII itself). */
    public void recordRedaction(String entityType, int count) {
        if (count <= 0) {
            return;
        }
        Counter.builder("atlas.gateway.redaction.count")
                .tag("entity_type", entityType)
                .register(registry)
                .increment(count);
    }
}
