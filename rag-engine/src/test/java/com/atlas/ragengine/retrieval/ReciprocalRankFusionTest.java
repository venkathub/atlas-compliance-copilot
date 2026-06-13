package com.atlas.ragengine.retrieval;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ReciprocalRankFusionTest {

    private static final UUID A = UUID.fromString("00000000-0000-0000-0000-0000000000a1");
    private static final UUID B = UUID.fromString("00000000-0000-0000-0000-0000000000b2");
    private static final UUID C = UUID.fromString("00000000-0000-0000-0000-0000000000c3");

    private final ReciprocalRankFusion rrf = new ReciprocalRankFusion(60);

    @Test
    void documentRankedHighInBothSourcesWins() {
        // A is rank 1 in dense and rank 1 in sparse; B/C appear in only one list
        List<RetrievedChunk> dense = List.of(chunk(A), chunk(B));
        List<RetrievedChunk> sparse = List.of(chunk(A), chunk(C));

        List<RetrievedChunk> fused = rrf.fuse(List.of(dense, sparse));

        assertThat(fused).extracting(RetrievedChunk::id).containsExactly(A, B, C); // A first
        // A's fused score = 1/61 + 1/61; B and C each = 1/61 + 1/62 (rank 2 in their single list)
        assertThat(fused.get(0).score()).isEqualTo(2.0 / 61);
        assertThat(fused.get(1).score()).isEqualTo(1.0 / 62);
    }

    @Test
    void mergesUnionOfAllCandidates() {
        List<RetrievedChunk> dense = List.of(chunk(A), chunk(B));
        List<RetrievedChunk> sparse = List.of(chunk(C));
        assertThat(rrf.fuse(List.of(dense, sparse)))
                .extracting(RetrievedChunk::id)
                .containsExactlyInAnyOrder(A, B, C);
    }

    @Test
    void orderingIsDeterministicOnScoreTies() {
        // B and C are both rank-1 in one list only -> equal scores -> tie-break by id ascending
        List<RetrievedChunk> dense = List.of(chunk(C));
        List<RetrievedChunk> sparse = List.of(chunk(B));
        List<RetrievedChunk> fused = rrf.fuse(List.of(dense, sparse));
        assertThat(fused).extracting(RetrievedChunk::id).containsExactly(B, C); // b2 < c3
    }

    @Test
    void higherKFlattensRankInfluence() {
        ReciprocalRankFusion small = new ReciprocalRankFusion(1);
        List<RetrievedChunk> dense = List.of(chunk(A), chunk(B));
        // with k=1, rank-1 (1/2) dominates rank-2 (1/3) strongly
        List<RetrievedChunk> fused = small.fuse(List.of(dense, List.of()));
        assertThat(fused.get(0).id()).isEqualTo(A);
        assertThat(fused.get(0).score()).isEqualTo(0.5);
        assertThat(fused.get(1).score()).isEqualTo(1.0 / 3);
    }

    private static RetrievedChunk chunk(UUID id) {
        return new RetrievedChunk(id, UUID.randomUUID(), "content-" + id, "public", Map.of(), 0.0);
    }
}
