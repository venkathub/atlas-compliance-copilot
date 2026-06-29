package com.atlas.ragengine.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.util.List;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.openai.OpenAiChatModel;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Configuration;

/**
 * LIVE proof that rag-engine's chat path actually generates via a real vLLM server when
 * {@code ATLAS_CHAT_BACKEND=vllm} — using the SAME {@link VllmChatConfig} the app wires
 * (so this is the bean {@code QueryService} would call), not a hand-rolled client.
 *
 * <p>No DB / no Ollama needed: it exercises only the chat backend. Embeddings-stay-on-Ollama is
 * covered by {@link VllmChatConfigTest} (no OpenAI EmbeddingModel bean) + the architecture.
 *
 * <p>Gated behind the {@code live} tag (needs a running vLLM endpoint):
 * <pre>set -a && . ./.env && set +a && mvn -P live -pl rag-engine -Dit.test=VllmChatLiveIT verify</pre>
 */
@Tag("live")
class VllmChatLiveIT {

    @Configuration
    @EnableConfigurationProperties(ChatBackendProperties.class)
    static class PropsEnabler {}

    @Test
    void ragEngineChatModelGeneratesViaVllm() {
        String baseUrl = System.getenv("ATLAS_VLLM_BASE_URL");
        String model = System.getenv().getOrDefault("ATLAS_VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct-AWQ");
        assumeTrue(baseUrl != null && !baseUrl.isBlank(),
                "ATLAS_VLLM_BASE_URL not set — skipping live vLLM proof");

        new ApplicationContextRunner()
                .withUserConfiguration(PropsEnabler.class, VllmChatConfig.class)
                .withPropertyValues(
                        "atlas.chat.backend=vllm",
                        "atlas.chat.vllm-base-url=" + baseUrl,
                        "atlas.chat.vllm-model=" + model)
                .run(ctx -> {
                    ChatModel chat = ctx.getBean(ChatModel.class);
                    // the @Primary bean the app injects is the OpenAI-compatible (vLLM) one
                    assertThat(chat).isInstanceOf(OpenAiChatModel.class);

                    ChatResponse resp = chat.call(new Prompt(List.of(
                            new UserMessage("Reply with exactly: ATLAS_OK"))));
                    String text = resp.getResult().getOutput().getText();
                    String served = resp.getMetadata() == null ? "" : resp.getMetadata().getModel();

                    System.out.println("[live] vLLM served model=" + served + " answer=" + text);
                    assertThat(text).contains("ATLAS_OK");        // real generation happened
                    assertThat(served).containsIgnoringCase("Qwen"); // …from the vLLM-served model
                });
    }
}
