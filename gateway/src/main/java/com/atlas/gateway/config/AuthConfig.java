package com.atlas.gateway.config;

import com.atlas.gateway.auth.ClearanceTokenService;
import com.atlas.gateway.auth.DevUserDirectory;
import com.atlas.gateway.auth.DownstreamClearanceSigner;
import com.atlas.gateway.auth.GatewayProperties;
import com.atlas.gateway.auth.IdpProperties;
import com.atlas.gateway.auth.JwtClearanceFilter;
import com.atlas.gateway.auth.ResourceScopedTokenIssuer;
import com.atlas.gateway.auth.ResourceTokenProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.core.Ordered;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Wires the simulated-IdP trust boundary (ADR-0034): the token service + dev directory behind
 * {@code POST /v1/auth/token}, the {@link JwtClearanceFilter} that validates the client JWT on every
 * protected request, and the {@link DownstreamClearanceSigner} that re-asserts the verified clearance
 * to {@code rag-engine}. All config is env-swappable via {@link IdpProperties}/{@link GatewayProperties}.
 */
@Configuration
@EnableConfigurationProperties({IdpProperties.class, GatewayProperties.class, ResourceTokenProperties.class})
public class AuthConfig {

    @Bean
    DevUserDirectory devUserDirectory(IdpProperties props) {
        return new DevUserDirectory(props.devUsers());
    }

    @Bean
    ClearanceTokenService clearanceTokenService(IdpProperties props) {
        return new ClearanceTokenService(props);
    }

    /** Resource-scoped (RFC 8707) token issuer for the MCP hop (ADR-0046, P4 task 5). Additive. */
    @Bean
    ResourceScopedTokenIssuer resourceScopedTokenIssuer(IdpProperties idp, ResourceTokenProperties resource) {
        return new ResourceScopedTokenIssuer(idp, resource);
    }

    @Bean
    DownstreamClearanceSigner downstreamClearanceSigner(GatewayProperties props) {
        return new DownstreamClearanceSigner(props);
    }

    /**
     * Register the trust-boundary filter early (before the dispatcher) for all routes; the filter
     * itself skips {@code /v1/auth/**} and {@code /actuator/**}.
     */
    @Bean
    FilterRegistrationBean<JwtClearanceFilter> jwtClearanceFilter(ClearanceTokenService tokens) {
        FilterRegistrationBean<JwtClearanceFilter> reg = new FilterRegistrationBean<>(new JwtClearanceFilter(tokens));
        reg.addUrlPatterns("/*");
        reg.setOrder(Ordered.HIGHEST_PRECEDENCE + 10);
        return reg;
    }
}
