package com.atlas.gateway.config;

import com.atlas.gateway.cache.CacheProperties;
import com.atlas.gateway.cache.NoOpSemanticCache;
import com.atlas.gateway.cache.OllamaQueryEmbedder;
import com.atlas.gateway.cache.QueryEmbedder;
import com.atlas.gateway.cache.RedisSemanticCache;
import com.atlas.gateway.cache.SemanticCache;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import redis.clients.jedis.JedisPooled;

/**
 * Wires the clearance-safe semantic cache (ADR-0036). When {@code atlas.cache.enabled=true} (default) a
 * RediSearch-backed cache is used; otherwise a {@link NoOpSemanticCache} (every lookup a miss). The
 * {@link JedisPooled} connects lazily (no connection at context start), so the gateway boots without Redis.
 */
@Configuration
@EnableConfigurationProperties(CacheProperties.class)
public class CacheConfig {

    @Bean
    QueryEmbedder queryEmbedder(EmbeddingModel embeddingModel) {
        return new OllamaQueryEmbedder(embeddingModel);
    }

    @Bean
    @ConditionalOnProperty(name = "atlas.cache.enabled", havingValue = "true", matchIfMissing = true)
    JedisPooled cacheJedis(@Value("${REDIS_HOST:localhost}") String host,
            @Value("${REDIS_PORT:6379}") int port) {
        return new JedisPooled(host, port);
    }

    @Bean
    @ConditionalOnProperty(name = "atlas.cache.enabled", havingValue = "true", matchIfMissing = true)
    SemanticCache redisSemanticCache(JedisPooled cacheJedis, CacheProperties props,
            @Value("${EMBED_DIM:768}") int embeddingDim) {
        return new RedisSemanticCache(cacheJedis, "atlas-cache-idx", embeddingDim,
                props.simThreshold(), props.ttlSeconds());
    }

    @Bean
    @ConditionalOnProperty(name = "atlas.cache.enabled", havingValue = "false")
    SemanticCache noOpSemanticCache() {
        return new NoOpSemanticCache();
    }
}
