package com.atlas.gateway.resilience;

/** No-op limiter (always allows) — wired when {@code atlas.resilience.rate-limit-enabled=false}. */
public class AllowAllRateLimiter implements RateLimiter {

    @Override
    public boolean tryAcquire(String key) {
        return true;
    }
}
