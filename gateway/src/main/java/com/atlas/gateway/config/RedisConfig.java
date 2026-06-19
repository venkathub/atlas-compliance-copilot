package com.atlas.gateway.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import redis.clients.jedis.JedisPooled;

/**
 * Shared Redis (Redis Stack) client for the gateway's Redis-backed features: the semantic cache
 * (ADR-0036), the token-bucket rate limiter, and the daily budget counters (ADR-0038, LLM10).
 *
 * <p>{@link JedisPooled} connects lazily (no connection at context start), so the gateway boots without
 * Redis — each feature only touches Redis when actually invoked, and each can be independently disabled.
 */
@Configuration
public class RedisConfig {

    @Bean(destroyMethod = "close")
    JedisPooled gatewayJedis(@Value("${REDIS_HOST:localhost}") String host,
            @Value("${REDIS_PORT:6379}") int port) {
        return new JedisPooled(host, port);
    }
}
