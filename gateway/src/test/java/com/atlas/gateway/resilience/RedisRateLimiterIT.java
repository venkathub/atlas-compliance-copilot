package com.atlas.gateway.resilience;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import redis.clients.jedis.JedisPooled;

/** Redis token-bucket rate-limiter enforcement (ADR-0038, LLM10) against real Redis. */
@Testcontainers
class RedisRateLimiterIT {

    @Container
    static final GenericContainer<?> REDIS =
            new GenericContainer<>(DockerImageName.parse("redis/redis-stack-server:7.4.0-v3"))
                    .withExposedPorts(6379);

    private static JedisPooled jedis;

    @BeforeAll
    static void connect() {
        jedis = new JedisPooled(REDIS.getHost(), REDIS.getMappedPort(6379));
    }

    @AfterAll
    static void close() {
        jedis.close();
    }

    @BeforeEach
    void flush() {
        jedis.flushAll();
    }

    @Test
    void allowsUpToCapacityThenBlocks() {
        RedisRateLimiter limiter = new RedisRateLimiter(jedis, 3); // 3 req/min
        assertThat(limiter.tryAcquire("priya")).isTrue();
        assertThat(limiter.tryAcquire("priya")).isTrue();
        assertThat(limiter.tryAcquire("priya")).isTrue();
        assertThat(limiter.tryAcquire("priya")).as("4th within the same minute is blocked").isFalse();
    }

    @Test
    void bucketsArePerCaller() {
        RedisRateLimiter limiter = new RedisRateLimiter(jedis, 1);
        assertThat(limiter.tryAcquire("priya")).isTrue();
        assertThat(limiter.tryAcquire("priya")).isFalse();
        assertThat(limiter.tryAcquire("analyst-bob")).as("a different caller has its own bucket").isTrue();
    }
}
