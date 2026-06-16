package com.atlas.gateway.config;

import com.atlas.gateway.auth.GatewayProperties;
import com.atlas.gateway.resilience.ResilienceProperties;
import java.time.Duration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

/**
 * Wires the downstream HTTP client the Gateway uses to proxy to {@code rag-engine}.
 *
 * <p>A blocking {@link RestClient} matches the WebMVC gateway idiom (ADR-0033). The read timeout is the
 * per-request timeout ({@code ATLAS_REQUEST_TIMEOUT_MS}, LLM10): a slow/stalled downstream trips the read
 * timeout, surfacing as an exception the {@code ModelCircuitBreaker} records as a failure (ADR-0039).
 */
@Configuration
public class DownstreamConfig {

    @Bean
    RestClient ragEngineRestClient(RestClient.Builder builder, GatewayProperties props,
            ResilienceProperties resilience) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(5));
        factory.setReadTimeout(Duration.ofMillis(resilience.requestTimeoutMs()));
        return builder
                .baseUrl(props.ragEngineUrl())
                .requestFactory(factory)
                .build();
    }
}
