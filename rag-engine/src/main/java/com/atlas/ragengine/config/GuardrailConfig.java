package com.atlas.ragengine.config;

import com.atlas.ragengine.guardrail.GuardrailProperties;
import com.atlas.ragengine.guardrail.InjectionGuardrail;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** Wires the prompt-injection guardrail (LLM01, ADR-0015). */
@Configuration
@EnableConfigurationProperties(GuardrailProperties.class)
public class GuardrailConfig {

    @Bean
    InjectionGuardrail injectionGuardrail(GuardrailProperties props) {
        return new InjectionGuardrail(props);
    }
}
