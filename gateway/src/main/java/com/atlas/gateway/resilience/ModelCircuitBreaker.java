package com.atlas.gateway.resilience;

import java.util.function.Supplier;
import org.springframework.cloud.client.circuitbreaker.CircuitBreaker;

/**
 * Wraps the rag-engine/model call in a Resilience4j circuit breaker (ADR-0039, LLM10). On a downstream
 * failure or timeout — or while the breaker is open — the fallback bounds the blast radius (R5) by throwing
 * a typed {@link DownstreamUnavailableException} ({@code 503} + {@code Retry-After}) instead of letting a
 * stalled GPU cascade into the gateway.
 *
 * <p>The per-request timeout is enforced by the downstream {@code RestClient} read timeout
 * ({@code ATLAS_REQUEST_TIMEOUT_MS}); a timeout surfaces as an exception the breaker records as a failure.
 */
public class ModelCircuitBreaker {

    private final CircuitBreaker breaker;
    private final long retryAfterSeconds;

    public ModelCircuitBreaker(CircuitBreaker breaker, long retryAfterSeconds) {
        this.breaker = breaker;
        this.retryAfterSeconds = retryAfterSeconds;
    }

    /** Run {@code action} through the breaker; on any failure throw {@link DownstreamUnavailableException}. */
    public <T> T call(Supplier<T> action) {
        return breaker.run(action, throwable -> {
            throw new DownstreamUnavailableException(retryAfterSeconds, throwable);
        });
    }
}
