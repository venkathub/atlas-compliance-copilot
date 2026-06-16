package com.atlas.gateway.cache;

import java.util.Optional;

/**
 * Clearance-partitioned, poison-resistant semantic cache (ADR-0036).
 *
 * <p>The RBAC invariant is <b>structural</b>: entries are partitioned by clearance, and a lookup can only
 * ever match within the caller's own clearance partition — a cross-clearance hit is impossible by
 * construction, not by a filter that could be misconfigured (the cross-clearance negative-cache hard gate,
 * R1). Writes are <b>trusted-write only</b>: the Gateway caches only answers the live RBAC + guardrail +
 * grounding path already produced. A {@code corpusVersion} mismatch is a miss (re-ingest invalidation).
 */
public interface SemanticCache {

    /** The payload cached for a query: the rag-engine answer (JSON) and the model that produced it. */
    record CachedAnswer(String answerJson, String model) {
    }

    /** A cache hit: the stored answer + the cosine similarity of the matched entry. */
    record CacheHit(String answerJson, String model, double similarity) {
    }

    /**
     * Look up a semantically-similar cached answer <b>within the caller's clearance partition</b>.
     *
     * @param clearance     the caller's <em>verified</em> clearance label (never client-supplied)
     * @param corpusVersion the current corpus version (mismatch ⇒ miss)
     * @param queryVec      the query embedding
     * @return a hit iff cosine-sim ≥ threshold AND same clearance AND same corpus version; else empty
     */
    Optional<CacheHit> lookup(String clearance, String corpusVersion, float[] queryVec);

    /** Store an answer in the caller's clearance partition with the configured TTL (trusted-write only). */
    void put(String clearance, String corpusVersion, float[] queryVec, CachedAnswer answer);
}
