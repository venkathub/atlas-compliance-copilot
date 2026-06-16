package com.atlas.gateway.resilience;

/** Per-caller request rate limiter (ADR-0038, LLM10). */
public interface RateLimiter {

    /**
     * Try to consume one token for {@code key} (typically the caller id).
     *
     * @return true if allowed, false if the caller is over their rate quota (→ 429)
     */
    boolean tryAcquire(String key);
}
