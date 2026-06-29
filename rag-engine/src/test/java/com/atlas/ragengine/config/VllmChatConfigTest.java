package com.atlas.ragengine.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.openai.OpenAiChatModel;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Configuration;

/**
 * Backend-selection wiring (offline, no GPU): default Ollama vs the conditional vLLM chat backend.
 * The live generation against a real vLLM server is proven separately by the {@code live}-tagged IT.
 */
class VllmChatConfigTest {

    private final ApplicationContextRunner runner = new ApplicationContextRunner()
            .withConfiguration(AutoConfigurations.of())
            .withUserConfiguration(PropsEnabler.class, VllmChatConfig.class);

    @Configuration
    @EnableConfigurationProperties(ChatBackendProperties.class)
    static class PropsEnabler {}

    @Test
    void vllmBackendActivatesPrimaryOpenAiChatModel() {
        runner.withPropertyValues(
                        "atlas.chat.backend=vllm",
                        "atlas.chat.vllm-base-url=https://vllm.example",
                        "atlas.chat.vllm-model=Qwen/Qwen2.5-7B-Instruct-AWQ")
                .run(ctx -> {
                    assertThat(ctx).hasSingleBean(ChatModel.class);
                    assertThat(ctx.getBean(ChatModel.class)).isInstanceOf(OpenAiChatModel.class);
                });
    }

    @Test
    void ollamaBackendLeavesVllmInert() {
        runner.withPropertyValues("atlas.chat.backend=ollama")
                .run(ctx -> assertThat(ctx).doesNotHaveBean("vllmChatModel"));
    }

    @Test
    void absentBackendLeavesVllmInert() {
        runner.run(ctx -> assertThat(ctx).doesNotHaveBean("vllmChatModel"));
    }

    @Test
    void vllmBackendRequiresBaseUrl() {
        ChatBackendProperties noUrl =
                new ChatBackendProperties("vllm", "", "model", "key");
        assertThatThrownBy(() -> new VllmChatConfig().vllmChatModel(noUrl))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("ATLAS_VLLM_BASE_URL");
    }

    @Test
    void isVllmHelper() {
        assertThat(new ChatBackendProperties("vllm", "u", "m", "k").isVllm()).isTrue();
        assertThat(new ChatBackendProperties("VLLM", "u", "m", "k").isVllm()).isTrue();
        assertThat(new ChatBackendProperties("ollama", null, null, null).isVllm()).isFalse();
        assertThat(new ChatBackendProperties(null, null, null, null).isVllm()).isFalse();
    }
}
