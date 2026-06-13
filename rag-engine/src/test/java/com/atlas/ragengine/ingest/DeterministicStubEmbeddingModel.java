package com.atlas.ragengine.ingest;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import org.springframework.ai.document.Document;
import org.springframework.ai.embedding.Embedding;
import org.springframework.ai.embedding.EmbeddingRequest;
import org.springframework.ai.embedding.EmbeddingResponse;
import org.springframework.ai.embedding.EmbeddingModel;

/**
 * Deterministic, offline stand-in for the Ollama {@link EmbeddingModel}. Produces a fixed-dimension
 * vector seeded by the input text, so ingestion ITs run in CI with Docker but <b>no GPU</b> and are
 * reproducible. The real embedding path is exercised by the live test (P1 task 7).
 */
public class DeterministicStubEmbeddingModel implements EmbeddingModel {

    private final int dim;

    public DeterministicStubEmbeddingModel(int dim) {
        this.dim = dim;
    }

    @Override
    public EmbeddingResponse call(EmbeddingRequest request) {
        List<Embedding> embeddings = new ArrayList<>();
        int index = 0;
        for (String input : request.getInstructions()) {
            embeddings.add(new Embedding(vectorFor(input), index++));
        }
        return new EmbeddingResponse(embeddings);
    }

    @Override
    public float[] embed(Document document) {
        return vectorFor(document.getText());
    }

    @Override
    public int dimensions() {
        return dim;
    }

    private float[] vectorFor(String text) {
        Random rnd = new Random(text == null ? 0 : text.hashCode());
        float[] v = new float[dim];
        for (int i = 0; i < dim; i++) {
            v[i] = rnd.nextFloat() * 2f - 1f; // [-1, 1)
        }
        return v;
    }
}
