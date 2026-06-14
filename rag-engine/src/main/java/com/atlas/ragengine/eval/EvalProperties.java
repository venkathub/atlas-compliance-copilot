package com.atlas.ragengine.eval;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Inline Spring AI evaluator config (ADR-0026 / D-P2-6). These run an extra LLM call per query, so
 * they are **OFF by default** (cost discipline) — they are a cheap per-request *trace annotation* and
 * smoke signal, never the gate (the Python RAGAS run is the authority).
 */
@ConfigurationProperties(prefix = "atlas.eval")
public record EvalProperties(Boolean inlineEnabled) {

    public EvalProperties {
        inlineEnabled = inlineEnabled != null && inlineEnabled;
    }

    public static EvalProperties defaults() {
        return new EvalProperties(false);
    }
}
