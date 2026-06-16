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

/** Redis daily-budget enforcement (ADR-0038, LLM10): pre-check + post-accounting against real Redis. */
@Testcontainers
class RedisBudgetGuardIT {

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
    void enforcesDailyCapAcrossPreCheckAndAccounting() {
        RedisBudgetGuard budget = new RedisBudgetGuard(jedis, 10.0); // cap = 10 units/day

        assertThat(budget.wouldExceed("priya", 5.0)).isFalse();
        budget.record("priya", 5.0);
        assertThat(budget.wouldExceed("priya", 5.0)).as("5+5=10 is at the cap, not over").isFalse();
        budget.record("priya", 5.0);
        assertThat(budget.wouldExceed("priya", 1.0)).as("10+1 exceeds the cap").isTrue();
    }

    @Test
    void budgetIsPerUser() {
        RedisBudgetGuard budget = new RedisBudgetGuard(jedis, 10.0);
        budget.record("priya", 10.0);
        assertThat(budget.wouldExceed("priya", 1.0)).isTrue();
        assertThat(budget.wouldExceed("analyst-bob", 1.0)).as("a different user has their own counter").isFalse();
    }
}
