package com.atlas.ragengine.probe;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;

/**
 * LIVE smoke test against the real remote Ollama endpoint ({@code OLLAMA_BASE_URL}).
 *
 * <p>Codifies the P0 exit-criteria connectivity gate: a chat completion comes back and an
 * embedding of the expected dimension comes back. Gated behind the {@code live} Maven
 * profile so normal CI never needs a GPU:
 * <pre>set -a && . ./.env && set +a && mvn -P live -pl rag-engine verify</pre>
 */
@Tag("live")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OllamaConnectivityLiveIT {

    @Autowired
    OllamaConnectivityProbe probe;

    @Value("${EMBED_DIM:768}")
    int expectedDim;

    @Test
    void chatCompletionReturnsText() {
        String reply = probe.chat("Reply with exactly: Atlas connectivity OK");
        assertThat(reply).isNotBlank();
    }

    @Test
    void embeddingHasExpectedDimension() {
        float[] embedding = probe.embed("Atlas embedding smoke test");
        assertThat(embedding).hasSize(expectedDim);
    }
}
