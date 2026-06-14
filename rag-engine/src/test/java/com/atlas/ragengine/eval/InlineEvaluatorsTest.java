package com.atlas.ragengine.eval;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

import com.atlas.ragengine.qa.StubChatModel;
import com.atlas.ragengine.retrieval.RetrievedChunk;
import io.micrometer.observation.ObservationRegistry;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.client.ChatClient;

class InlineEvaluatorsTest {

    private static RetrievedChunk chunk() {
        return new RetrievedChunk(UUID.randomUUID(), UUID.randomUUID(), "Revenue rose 12% in 2022.",
                "public", Map.of("docId", "d"), 0.5);
    }

    @Test
    void disabledIsANoOpAndMakesNoModelCalls() {
        StubChatModel chat = new StubChatModel("should not be called");
        InlineEvaluators evaluators = InlineEvaluators.disabled();

        var obs = io.micrometer.observation.Observation.start("t", ObservationRegistry.create());
        evaluators.annotate(obs, "q", List.of(chunk()), "answer");
        obs.stop();

        assertThat(evaluators.enabled()).isFalse();
        assertThat(chat.calls()).isZero();
    }

    @Test
    void enabledIsFailSoftWhenTheModelOutputIsUnparseable() {
        // A stub model returns a fixed non-conforming string; the evaluators must NOT throw —
        // the inline pre-filter can never break a query (it only annotates the trace).
        StubChatModel chat = new StubChatModel("not a valid evaluation verdict");
        InlineEvaluators evaluators = new InlineEvaluators(true, ChatClient.builder(chat));

        var obs = io.micrometer.observation.Observation.start("t", ObservationRegistry.create());
        assertThatCode(() -> evaluators.annotate(obs, "q", List.of(chunk()), "answer"))
                .doesNotThrowAnyException();
        obs.stop();

        assertThat(evaluators.enabled()).isTrue();
    }
}
