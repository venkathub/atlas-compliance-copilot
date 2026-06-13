package com.atlas.ragengine.probe;

import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.stereotype.Component;

/**
 * P0 connectivity probe.
 *
 * <p>Proves the Spring AI &harr; remote Ollama path end-to-end: one chat completion
 * and one embedding via the env-configured endpoint ({@code OLLAMA_BASE_URL}). There is
 * deliberately no RAG logic here — that arrives in P1. Models are injected by Spring AI
 * auto-configuration and are fully env-swappable (never hardcoded).
 */
@Component
public class OllamaConnectivityProbe {

    private final ChatModel chatModel;
    private final EmbeddingModel embeddingModel;

    public OllamaConnectivityProbe(ChatModel chatModel, EmbeddingModel embeddingModel) {
        this.chatModel = chatModel;
        this.embeddingModel = embeddingModel;
    }

    /** One-shot chat completion against the remote model. */
    public String chat(String prompt) {
        return chatModel.call(prompt);
    }

    /** One-shot embedding; returns the raw vector so callers can assert its dimension. */
    public float[] embed(String text) {
        return embeddingModel.embed(text);
    }
}
