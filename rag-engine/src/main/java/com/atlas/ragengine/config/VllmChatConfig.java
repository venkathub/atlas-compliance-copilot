package com.atlas.ragengine.config;

import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.openai.OpenAiChatModel;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.ai.openai.api.OpenAiApi;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

/**
 * Activates an OpenAI-compatible (vLLM) chat backend when {@code atlas.chat.backend=vllm}.
 *
 * <p>Builds a {@link ChatModel} from the Spring AI OpenAI <i>model</i> module manually (not the
 * Boot starter), so it does NOT auto-configure an OpenAI {@code EmbeddingModel} — embeddings stay
 * on the Ollama starter's bean. The bean is {@link Primary} so every chat consumer
 * (QueryService, LlmReranker, the connectivity probe, the inline-eval ChatClient.Builder) uses
 * vLLM while the Ollama {@code ChatModel} remains present but unused. When the property is absent
 * or {@code ollama}, this config is inert and the Ollama auto-config wins. See ADR-0068.
 *
 * <p>The per-request tier override in {@code QueryService} uses portable {@code ChatOptions}
 * (model name as a String), so {@code X-Atlas-Model-Tier} keeps working against vLLM — point the
 * tier model ids at vLLM-served models.
 */
@Configuration
@ConditionalOnProperty(name = "atlas.chat.backend", havingValue = "vllm")
@EnableConfigurationProperties(ChatBackendProperties.class)
public class VllmChatConfig {

    @Bean
    @Primary
    ChatModel vllmChatModel(ChatBackendProperties props) {
        if (props.vllmBaseUrl() == null || props.vllmBaseUrl().isBlank()) {
            throw new IllegalStateException(
                    "atlas.chat.backend=vllm requires ATLAS_VLLM_BASE_URL (the vLLM /v1 host)");
        }
        if (props.vllmModel() == null || props.vllmModel().isBlank()) {
            throw new IllegalStateException(
                    "atlas.chat.backend=vllm requires ATLAS_VLLM_MODEL");
        }
        OpenAiApi api = OpenAiApi.builder()
                .baseUrl(props.vllmBaseUrl())
                .apiKey(props.vllmApiKey() == null || props.vllmApiKey().isBlank()
                        ? "not-needed" : props.vllmApiKey())
                .build();
        OpenAiChatOptions options = OpenAiChatOptions.builder()
                .model(props.vllmModel())
                .temperature(0.0)
                .build();
        return OpenAiChatModel.builder().openAiApi(api).defaultOptions(options).build();
    }
}
