package com.atlas.gateway.cache;

/** Embeds a query for the semantic cache (ADR-0036). Abstracted so tests are model-free. */
public interface QueryEmbedder {

    /** @return the embedding vector for {@code text} (e.g. 768-dim nomic-embed-text). */
    float[] embed(String text);
}
