package com.atlas.gateway.config;

import com.atlas.gateway.resilience.AllowAllRateLimiter;
import com.atlas.gateway.resilience.BudgetGuard;
import com.atlas.gateway.resilience.ModelCircuitBreaker;
import com.atlas.gateway.resilience.NoOpBudgetGuard;
import com.atlas.gateway.resilience.RateLimiter;
import com.atlas.gateway.resilience.RedisBudgetGuard;
import com.atlas.gateway.resilience.RedisRateLimiter;
import com.atlas.gateway.resilience.RequestLimits;
import com.atlas.gateway.resilience.ResilienceProperties;
import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import java.time.Duration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.cloud.circuitbreaker.resilience4j.Resilience4JCircuitBreakerFactory;
import org.springframework.cloud.circuitbreaker.resilience4j.Resilience4JConfigBuilder;
import org.springframework.cloud.client.circuitbreaker.Customizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import redis.clients.jedis.JedisPooled;

/**
 * Wires the gateway resource controls (ADR-0038/0039, OWASP LLM10): per-user rate limiter + daily budget
 * (Redis-backed, independently toggleable so the gateway runs Redis-free when disabled), the per-request
 * limits, and the Resilience4j circuit breaker around the rag-engine call.
 */
@Configuration
@EnableConfigurationProperties(ResilienceProperties.class)
public class ResilienceConfig {

    @Bean
    @ConditionalOnProperty(name = "atlas.resilience.rate-limit-enabled", havingValue = "true", matchIfMissing = true)
    RateLimiter redisRateLimiter(JedisPooled gatewayJedis, ResilienceProperties props) {
        return new RedisRateLimiter(gatewayJedis, props.requestsPerMin());
    }

    @Bean
    @ConditionalOnProperty(name = "atlas.resilience.rate-limit-enabled", havingValue = "false")
    RateLimiter allowAllRateLimiter() {
        return new AllowAllRateLimiter();
    }

    @Bean
    @ConditionalOnProperty(name = "atlas.resilience.budget-enabled", havingValue = "true", matchIfMissing = true)
    BudgetGuard redisBudgetGuard(JedisPooled gatewayJedis, ResilienceProperties props) {
        return new RedisBudgetGuard(gatewayJedis, props.budgetDailyCapUnits());
    }

    @Bean
    @ConditionalOnProperty(name = "atlas.resilience.budget-enabled", havingValue = "false")
    BudgetGuard noOpBudgetGuard() {
        return new NoOpBudgetGuard();
    }

    @Bean
    RequestLimits requestLimits(ResilienceProperties props) {
        return new RequestLimits(props.maxInputTokens(), props.maxOutputTokens());
    }

    /** Tune the breaker from config; applied to the {@code rag-engine} instance. */
    @Bean
    Customizer<Resilience4JCircuitBreakerFactory> circuitBreakerCustomizer(ResilienceProperties props) {
        return factory -> factory.configureDefault(id -> new Resilience4JConfigBuilder(id)
                .circuitBreakerConfig(CircuitBreakerConfig.custom()
                        .failureRateThreshold(props.cbFailureRateThresholdPct())
                        .waitDurationInOpenState(Duration.ofMillis(props.cbWaitDurationMs()))
                        .slidingWindowSize(10)
                        .build())
                .build());
    }

    @Bean
    ModelCircuitBreaker modelCircuitBreaker(Resilience4JCircuitBreakerFactory factory,
            ResilienceProperties props) {
        return new ModelCircuitBreaker(factory.create("rag-engine"),
                Math.max(1, props.cbWaitDurationMs() / 1000));
    }
}
