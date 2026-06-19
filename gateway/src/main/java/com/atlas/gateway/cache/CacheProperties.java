package com.atlas.gateway.cache;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Clearance-partitioned, poison-resistant semantic-cache configuration (ADR-0036). Env-swappable.
 *
 * @param enabled       master switch ({@code ATLAS_CACHE_ENABLED}); when off, a no-op cache is wired
 * @param simThreshold  cosine-similarity hit threshold ({@code ATLAS_CACHE_SIM_THRESHOLD}); kept tight to
 *                      resist wrong-but-similar collisions; eval-calibrated in task 10 → gateway-baseline.json
 * @param ttlSeconds    per-entry TTL ({@code ATLAS_CACHE_TTL_SECONDS}) — native Redis EXPIRE
 * @param corpusVersion current corpus version tag ({@code ATLAS_CACHE_CORPUS_VERSION}); a mismatch is a miss,
 *                      so bumping it on re-ingest invalidates the cache
 * @param regroundOnHit optional cheap re-grounding on a hit (reserved; not yet wired — ADR-0036)
 */
@ConfigurationProperties(prefix = "atlas.cache")
public record CacheProperties(
        boolean enabled,
        double simThreshold,
        long ttlSeconds,
        String corpusVersion,
        boolean regroundOnHit) {

    public CacheProperties {
        simThreshold = simThreshold > 0 ? simThreshold : 0.95;
        ttlSeconds = ttlSeconds > 0 ? ttlSeconds : 86_400L;
        corpusVersion = (corpusVersion == null || corpusVersion.isBlank()) ? "v1" : corpusVersion;
    }
}
