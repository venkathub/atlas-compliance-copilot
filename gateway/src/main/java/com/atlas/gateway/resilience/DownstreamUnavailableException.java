package com.atlas.gateway.resilience;

/**
 * Thrown when the rag-engine/model call fails or the circuit breaker is open (ADR-0039). Mapped to a typed
 * {@code 503 Service Unavailable} + {@code Retry-After} by {@code GatewayExceptionHandler}.
 */
public class DownstreamUnavailableException extends RuntimeException {

    private final long retryAfterSeconds;

    public DownstreamUnavailableException(long retryAfterSeconds, Throwable cause) {
        super("rag-engine unavailable", cause);
        this.retryAfterSeconds = retryAfterSeconds;
    }

    public long retryAfterSeconds() {
        return retryAfterSeconds;
    }
}
