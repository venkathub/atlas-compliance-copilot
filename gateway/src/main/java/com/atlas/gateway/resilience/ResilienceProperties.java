package com.atlas.gateway.resilience;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Gateway resource-control configuration (ADR-0038/0039, OWASP LLM10 Unbounded Consumption). All
 * env-swappable.
 *
 * @param rateLimitEnabled       master switch for the per-user rate limiter ({@code ATLAS_RATELIMIT_ENABLED})
 * @param requestsPerMin         token-bucket capacity/refill per minute ({@code ATLAS_RATELIMIT_REQUESTS_PER_MIN})
 * @param budgetEnabled          master switch for the per-user daily budget ({@code ATLAS_BUDGET_ENABLED})
 * @param budgetDailyCapUnits     per-user daily spend cap in cost-units ({@code ATLAS_BUDGET_DAILY_CAP_UNITS})
 * @param maxInputTokens          per-request input-size cap ({@code ATLAS_MAX_INPUT_TOKENS}); over → 413
 * @param maxOutputTokens         per-request generation cap forwarded to rag-engine ({@code ATLAS_MAX_OUTPUT_TOKENS})
 * @param requestTimeoutMs        downstream call timeout ({@code ATLAS_REQUEST_TIMEOUT_MS})
 * @param cbFailureRateThresholdPct breaker trip threshold ({@code ATLAS_CB_FAILURE_RATE_THRESHOLD_PCT})
 * @param cbWaitDurationMs        breaker open→half-open wait ({@code ATLAS_CB_WAIT_DURATION_MS})
 */
@ConfigurationProperties(prefix = "atlas.resilience")
public record ResilienceProperties(
        boolean rateLimitEnabled,
        int requestsPerMin,
        boolean budgetEnabled,
        double budgetDailyCapUnits,
        int maxInputTokens,
        int maxOutputTokens,
        long requestTimeoutMs,
        float cbFailureRateThresholdPct,
        long cbWaitDurationMs) {

    public ResilienceProperties {
        requestsPerMin = requestsPerMin > 0 ? requestsPerMin : 60;
        budgetDailyCapUnits = budgetDailyCapUnits > 0 ? budgetDailyCapUnits : 100.0;
        maxInputTokens = maxInputTokens > 0 ? maxInputTokens : 6000;
        maxOutputTokens = maxOutputTokens > 0 ? maxOutputTokens : 1024;
        requestTimeoutMs = requestTimeoutMs > 0 ? requestTimeoutMs : 30_000L;
        cbFailureRateThresholdPct = cbFailureRateThresholdPct > 0 ? cbFailureRateThresholdPct : 50f;
        cbWaitDurationMs = cbWaitDurationMs > 0 ? cbWaitDurationMs : 10_000L;
    }
}
