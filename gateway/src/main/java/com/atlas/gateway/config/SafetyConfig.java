package com.atlas.gateway.config;

import com.atlas.gateway.safety.OutputSanitizer;
import com.atlas.gateway.safety.PiiRedactor;
import com.atlas.gateway.safety.SafetyProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Wires the egress safety controls (ADR-0037, OWASP LLM02/LLM05): the deterministic PII redactor and the
 * output sanitizer that run inline on the hot path before any answer leaves the gateway.
 */
@Configuration
@EnableConfigurationProperties(SafetyProperties.class)
public class SafetyConfig {

    @Bean
    PiiRedactor piiRedactor(SafetyProperties props) {
        return new PiiRedactor(props.nameDenylist());
    }

    @Bean
    OutputSanitizer outputSanitizer() {
        return new OutputSanitizer();
    }
}
