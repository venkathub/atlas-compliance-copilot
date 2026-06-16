package com.atlas.gateway.cache;

import java.util.Optional;

/** No-op cache used when {@code atlas.cache.enabled=false} (or no Redis): every lookup is a miss. */
public class NoOpSemanticCache implements SemanticCache {

    @Override
    public Optional<CacheHit> lookup(String clearance, String corpusVersion, float[] queryVec) {
        return Optional.empty();
    }

    @Override
    public void put(String clearance, String corpusVersion, float[] queryVec, CachedAnswer answer) {
        // intentionally no-op
    }
}
