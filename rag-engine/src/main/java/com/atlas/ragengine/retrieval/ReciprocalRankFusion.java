package com.atlas.ragengine.retrieval;

import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Reciprocal Rank Fusion (ADR-0013). Merges several ranked candidate lists (here: dense + sparse)
 * into one ranking by summing {@code 1 / (k + rank)} across lists, with {@code rank} 1-based.
 * Score-scale agnostic (no weight tuning), robust, and deterministic — ties break by chunk id.
 */
public class ReciprocalRankFusion {

    private final int k;

    public ReciprocalRankFusion(int k) {
        if (k <= 0) {
            throw new IllegalArgumentException("RRF k must be > 0");
        }
        this.k = k;
    }

    /** Fuse the given ranked lists into one RRF-ordered list (highest fused score first). */
    public List<RetrievedChunk> fuse(List<List<RetrievedChunk>> rankedLists) {
        Map<UUID, Double> fusedScore = new HashMap<>();
        Map<UUID, RetrievedChunk> representative = new LinkedHashMap<>();

        for (List<RetrievedChunk> list : rankedLists) {
            for (int i = 0; i < list.size(); i++) {
                RetrievedChunk chunk = list.get(i);
                int rank = i + 1;
                fusedScore.merge(chunk.id(), 1.0 / (k + rank), Double::sum);
                representative.putIfAbsent(chunk.id(), chunk);
            }
        }

        return representative.values().stream()
                .map(c -> c.withScore(fusedScore.get(c.id())))
                .sorted(Comparator.comparingDouble(RetrievedChunk::score).reversed()
                        .thenComparing(c -> c.id().toString()))
                .toList();
    }
}
