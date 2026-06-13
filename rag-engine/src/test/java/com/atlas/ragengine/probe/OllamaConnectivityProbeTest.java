package com.atlas.ragengine.probe;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.embedding.EmbeddingModel;

/**
 * Pure unit test — no Spring context, no network. Runs in CI on every PR.
 * Verifies the probe delegates to the injected Spring AI models.
 */
class OllamaConnectivityProbeTest {

    @Test
    void delegatesChatAndEmbedToModels() {
        ChatModel chatModel = mock(ChatModel.class);
        EmbeddingModel embeddingModel = mock(EmbeddingModel.class);
        when(chatModel.call("ping")).thenReturn("Atlas connectivity OK");
        when(embeddingModel.embed("ping")).thenReturn(new float[768]);

        OllamaConnectivityProbe probe = new OllamaConnectivityProbe(chatModel, embeddingModel);

        assertThat(probe.chat("ping")).isEqualTo("Atlas connectivity OK");
        assertThat(probe.embed("ping")).hasSize(768);
    }
}
