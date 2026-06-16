package com.atlas.gateway.cache;

import org.springframework.ai.embedding.EmbeddingModel;

/**
 * {@link QueryEmbedder} backed by Spring AI's Ollama {@link EmbeddingModel} (nomic-embed-text on the
 * remote {@code OLLAMA_BASE_URL}, ADR-0005/0036). The model never runs locally (CLAUDE.md).
 */
public class OllamaQueryEmbedder implements QueryEmbedder {

    private final EmbeddingModel embeddingModel;

    public OllamaQueryEmbedder(EmbeddingModel embeddingModel) {
        this.embeddingModel = embeddingModel;
    }

    @Override
    public float[] embed(String text) {
        return embeddingModel.embed(text);
    }
}
