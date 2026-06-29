package com.atlas.ragengine.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Selects the chat (generation) backend and configures the vLLM/OpenAI-compatible client.
 *
 * <p>Atlas defaults to Spring AI's <b>Ollama</b> client (native {@code /api/chat}). Setting
 * {@code atlas.chat.backend=vllm} (env {@code ATLAS_CHAT_BACKEND}) swaps the chat
 * {@code ChatModel} to an OpenAI-compatible client pointed at a vLLM server's {@code /v1}
 * endpoint. <b>Embeddings always stay on Ollama</b> (nomic-embed, 768-dim pgvector) — only
 * generation moves. See ADR-0068.
 */
@ConfigurationProperties(prefix = "atlas.chat")
public record ChatBackendProperties(
        /** {@code ollama} (default, native) or {@code vllm} (OpenAI-compatible). */
        String backend,
        /** vLLM server base URL (host root; the client appends {@code /v1/chat/completions}). */
        String vllmBaseUrl,
        /** Model id the vLLM server serves, e.g. {@code Qwen/Qwen2.5-7B-Instruct-AWQ}. */
        String vllmModel,
        /** API key — self-hosted vLLM ignores it; sent for protocol parity. */
        String vllmApiKey) {

    public boolean isVllm() {
        return "vllm".equalsIgnoreCase(backend == null ? "" : backend.strip());
    }
}
