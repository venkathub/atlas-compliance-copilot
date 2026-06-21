package com.atlas.mcptools.auth;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimNames;
import org.springframework.security.oauth2.jwt.JwtClaimValidator;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtIssuerValidator;
import org.springframework.security.oauth2.jwt.JwtTimestampValidator;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Secures the MCP tool server as an <b>OAuth 2.1 resource server</b> (ADR-0046 / D-P4-6). The {@code /mcp}
 * Streamable-HTTP endpoint requires an audience-restricted (RFC 8707) Bearer JWT: the {@link JwtDecoder}
 * validates signature (HS256), {@code exp}, {@code iss}, and {@code aud}. Actuator stays open for health
 * checks. Insufficient <em>clearance</em> is NOT a 401 here — that is a per-call tool re-check
 * ({@link ClearanceRecheck}) that returns an MCP error + a {@code DENIED} audit row (LLM06).
 */
@Configuration
@EnableWebSecurity
@EnableConfigurationProperties(McpTokenProperties.class)
public class ResourceServerConfig {

    @Bean
    SecurityFilterChain mcpSecurityFilterChain(HttpSecurity http, JwtDecoder jwtDecoder) throws Exception {
        http
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/actuator/**").permitAll()
                        .requestMatchers("/mcp/**").authenticated()
                        .anyRequest().permitAll())
                .oauth2ResourceServer(oauth2 -> oauth2.jwt(jwt -> jwt.decoder(jwtDecoder)))
                .csrf(csrf -> csrf.disable())
                .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS));
        return http.build();
    }

    @Bean
    JwtDecoder jwtDecoder(McpTokenProperties props) {
        SecretKey key = new SecretKeySpec(SecurityKeys.deriveHs256(props.signingKey()), "HmacSHA256");
        NimbusJwtDecoder decoder = NimbusJwtDecoder.withSecretKey(key)
                .macAlgorithm(MacAlgorithm.HS256)
                .build();
        OAuth2TokenValidator<Jwt> validators = new DelegatingOAuth2TokenValidator<>(
                new JwtTimestampValidator(),
                new JwtIssuerValidator(props.issuer()),
                audienceValidator(props.audience()));
        decoder.setJwtValidator(validators);
        return decoder;
    }

    /** RFC 8707: the token's {@code aud} must name this resource server. */
    private static OAuth2TokenValidator<Jwt> audienceValidator(String expectedAudience) {
        return new JwtClaimValidator<java.util.List<String>>(JwtClaimNames.AUD,
                aud -> aud != null && aud.contains(expectedAudience));
    }
}
