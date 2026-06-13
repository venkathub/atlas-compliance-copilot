package com.atlas.ragengine;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Atlas RAG Engine.
 *
 * <p>P0 scope: this is a thin module hosting only the Ollama <b>connectivity probe</b>
 * (no retrieval logic). The full permission-aware RAG engine is built in P1.
 */
@SpringBootApplication
public class RagEngineApplication {

    public static void main(String[] args) {
        SpringApplication.run(RagEngineApplication.class, args);
    }
}
