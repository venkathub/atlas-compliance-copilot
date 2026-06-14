package com.atlas.ragengine.config;

import com.atlas.ragengine.eval.EvalProperties;
import com.atlas.ragengine.eval.InlineEvaluators;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Wires the Spring AI inline evaluators (ADR-0026 / D-P2-6) — a cheap, OFF-by-default per-request
 * pre-filter that annotates the trace; the authoritative gate is the Python RAGAS run.
 */
@Configuration
@EnableConfigurationProperties(EvalProperties.class)
public class EvalConfig {

    @Bean
    InlineEvaluators inlineEvaluators(EvalProperties props, ChatClient.Builder chatClientBuilder) {
        return new InlineEvaluators(props.inlineEnabled(), chatClientBuilder);
    }
}
