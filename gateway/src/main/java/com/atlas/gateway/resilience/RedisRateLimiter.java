package com.atlas.gateway.resilience;

import java.util.List;
import redis.clients.jedis.JedisPooled;

/**
 * Distributed token-bucket rate limiter (ADR-0038, LLM10) — an atomic Redis Lua script so concurrent
 * requests can't race past the quota and bucket state survives restarts. Capacity = {@code requestsPerMin},
 * refilled continuously over the minute. Key {@code atlas:ratelimit:<caller>}.
 */
public class RedisRateLimiter implements RateLimiter {

    // Refill-on-read token bucket. Tokens regenerate at capacity/60000 per ms up to capacity.
    private static final String LUA = """
            local key = KEYS[1]
            local capacity = tonumber(ARGV[1])
            local refillPerMs = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])
            local ttl = tonumber(ARGV[4])
            local data = redis.call('HMGET', key, 'tokens', 'ts')
            local tokens = tonumber(data[1])
            local ts = tonumber(data[2])
            if tokens == nil then tokens = capacity; ts = now end
            local elapsed = now - ts
            if elapsed < 0 then elapsed = 0 end
            tokens = math.min(capacity, tokens + elapsed * refillPerMs)
            local allowed = 0
            if tokens >= 1 then tokens = tokens - 1; allowed = 1 end
            redis.call('HSET', key, 'tokens', tokens, 'ts', now)
            redis.call('EXPIRE', key, ttl)
            return allowed
            """;

    private static final long TTL_SECONDS = 120;
    private static final String KEY_PREFIX = "atlas:ratelimit:";

    private final JedisPooled jedis;
    private final int capacity;
    private final double refillPerMs;

    public RedisRateLimiter(JedisPooled jedis, int requestsPerMin) {
        this.jedis = jedis;
        this.capacity = requestsPerMin;
        this.refillPerMs = requestsPerMin / 60_000.0;
    }

    @Override
    public boolean tryAcquire(String key) {
        Object result = jedis.eval(LUA,
                List.of(KEY_PREFIX + key),
                List.of(Integer.toString(capacity), Double.toString(refillPerMs),
                        Long.toString(System.currentTimeMillis()), Long.toString(TTL_SECONDS)));
        return result instanceof Long allowed && allowed == 1L;
    }
}
