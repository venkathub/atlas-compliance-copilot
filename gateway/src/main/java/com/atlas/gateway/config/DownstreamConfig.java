package com.atlas.gateway.config;

import com.atlas.gateway.auth.GatewayProperties;
import java.time.Duration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

/**
 * Wires the downstream HTTP client the Gateway uses to proxy to {@code rag-engine} (P3 task 3).
 *
 * <p>A blocking {@link RestClient} matches the WebMVC gateway idiom (ADR-0033). Modest connect/read
 * timeouts are set here as a sane default; the <em>configurable</em> per-request timeout
 * ({@code ATLAS_REQUEST_TIMEOUT_MS}) and the Resilience4j circuit breaker that wraps this call are
 * added in P3 task 6 (LLM10).
 */
@Configuration
public class DownstreamConfig {

    @Bean
    RestClient ragEngineRestClient(RestClient.Builder builder, GatewayProperties props) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(5));
        factory.setReadTimeout(Duration.ofSeconds(30));
        return builder
                .baseUrl(props.ragEngineUrl())
                .requestFactory(factory)
                .build();
    }
}
