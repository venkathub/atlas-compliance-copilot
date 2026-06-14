package com.atlas.ragengine.retrieval;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.qa.StubChatModel;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class LlmRerankerTest {

    private static RetrievedChunk chunk(String docId) {
        return new RetrievedChunk(UUID.randomUUID(), UUID.randomUUID(), "content " + docId, "public",
                Map.of("docId", docId), 0.5);
    }

    @Test
    void reordersAccordingToModelOrderAndTruncates() {
        List<RetrievedChunk> fused = List.of(chunk("a"), chunk("b"), chunk("c"));
        // model says passage 3 then 1 then 2 (1-based)
        Reranker r = new LlmReranker(new StubChatModel("[3,1,2]"));

        List<RetrievedChunk> out = r.rerank("q", fused, 2);

        assertThat(out).extracting(RetrievedChunk::docId).containsExactly("c", "a");
    }

    @Test
    void appendsIndicesTheModelOmitted() {
        List<RetrievedChunk> fused = List.of(chunk("a"), chunk("b"), chunk("c"));
        Reranker r = new LlmReranker(new StubChatModel("[2]")); // only mentions passage 2

        List<RetrievedChunk> out = r.rerank("q", fused, 3);

        // 2 first, then the omitted 1 and 3 appended in original order
        assertThat(out).extracting(RetrievedChunk::docId).containsExactly("b", "a", "c");
    }

    @Test
    void fallsBackToRrfOrderOnUnparseableResponse() {
        List<RetrievedChunk> fused = List.of(chunk("a"), chunk("b"));
        Reranker r = new LlmReranker(new StubChatModel("I cannot do that."));

        List<RetrievedChunk> out = r.rerank("q", fused, 2);

        assertThat(out).extracting(RetrievedChunk::docId).containsExactly("a", "b");
    }

    @Test
    void neverIntroducesChunksOutsideTheCandidateSet() {
        List<RetrievedChunk> fused = List.of(chunk("a"), chunk("b"));
        // model hallucinates passage 9 (out of range) — must be ignored
        Reranker r = new LlmReranker(new StubChatModel("[9, 2, 1]"));

        List<RetrievedChunk> out = r.rerank("q", fused, 5);

        assertThat(out).extracting(RetrievedChunk::docId).containsExactlyInAnyOrder("a", "b");
        assertThat(out).hasSize(2);
    }
}
