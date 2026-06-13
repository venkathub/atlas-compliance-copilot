package com.atlas.ragengine.probe;

import java.util.LinkedHashMap;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Exposes the connectivity probe over HTTP for a 30-second manual demo:
 * {@code GET /probe/connectivity}.
 *
 * <p>NOTE: this endpoint calls the remote GPU and is NOT a liveness check — use
 * {@code /actuator/health} for liveness. Kept separate so health checks stay cheap.
 */
@RestController
@RequestMapping("/probe")
public class ProbeController {

    private final OllamaConnectivityProbe probe;
    private final String chatModelName;
    private final String embedModelName;
    private final int expectedDim;

    public ProbeController(
            OllamaConnectivityProbe probe,
            @Value("${spring.ai.ollama.chat.options.model:unknown}") String chatModelName,
            @Value("${spring.ai.ollama.embedding.options.model:unknown}") String embedModelName,
            @Value("${EMBED_DIM:768}") int expectedDim) {
        this.probe = probe;
        this.chatModelName = chatModelName;
        this.embedModelName = embedModelName;
        this.expectedDim = expectedDim;
    }

    @GetMapping("/connectivity")
    public Map<String, Object> connectivity() {
        String reply = probe.chat("Reply with exactly: Atlas connectivity OK").strip();
        float[] embedding = probe.embed("Atlas embedding smoke test");

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("ok", embedding.length == expectedDim && !reply.isBlank());
        body.put("chatModel", chatModelName);
        body.put("chatReply", reply);
        body.put("embeddingModel", embedModelName);
        body.put("embeddingDim", embedding.length);
        body.put("expectedDim", expectedDim);
        return body;
    }
}
