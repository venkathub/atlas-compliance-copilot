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
import io.github.resilience4j.timelimiter.TimeLimiterConfig;
import java.time.Duration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.cloud.circuitbreaker.resilience4j.Resilience4JCircuitBreakerFactory;
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

    /**
     * Configure the {@code rag-engine} circuit-breaker instance directly on the resilience4j registries and
     * create it.
     *
     * <p>P4 Task 0 (ADR-0050): on Spring Cloud 2025.0 / spring-cloud-circuitbreaker 3.3.x,
     * {@code Resilience4JCircuitBreakerFactory.create(id)} resolves both the circuit-breaker and
     * time-limiter configs from the resilience4j <em>registries</em> ({@code getConfiguration(id)} →
     * registry default), and <em>ignores</em> the factory's {@code configureDefault(..)} map (the
     * mechanism the old 2024.0 train used via a {@code Customizer} bean). Registering a named
     * {@code "rag-engine"} configuration in each registry here is the order-independent, version-correct
     * way to keep the breaker's TimeLimiter aligned with the per-request timeout
     * ({@code ATLAS_REQUEST_TIMEOUT_MS}) — otherwise every call falls back to Resilience4j's 1s default
     * TimeLimiter and a normal multi-second model call would wrongly trip the breaker (ADR-0039, LLM10).
     */
    @Bean
    ModelCircuitBreaker modelCircuitBreaker(Resilience4JCircuitBreakerFactory factory,
            ResilienceProperties props) {
        factory.getCircuitBreakerRegistry().addConfiguration("rag-engine", CircuitBreakerConfig.custom()
                .failureRateThreshold(props.cbFailureRateThresholdPct())
                .waitDurationInOpenState(Duration.ofMillis(props.cbWaitDurationMs()))
                .slidingWindowSize(10)
                .build());
        factory.getTimeLimiterRegistry().addConfiguration("rag-engine", TimeLimiterConfig.custom()
                .timeoutDuration(Duration.ofMillis(props.requestTimeoutMs()))
                .build());
        return new ModelCircuitBreaker(factory.create("rag-engine"),
                Math.max(1, props.cbWaitDurationMs() / 1000));
    }
}
