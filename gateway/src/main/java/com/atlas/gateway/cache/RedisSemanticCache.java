package com.atlas.gateway.cache;

import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import redis.clients.jedis.JedisPooled;
import redis.clients.jedis.exceptions.JedisDataException;
import redis.clients.jedis.search.Document;
import redis.clients.jedis.search.FTCreateParams;
import redis.clients.jedis.search.IndexDataType;
import redis.clients.jedis.search.Query;
import redis.clients.jedis.search.SearchResult;
import redis.clients.jedis.search.schemafields.TagField;
import redis.clients.jedis.search.schemafields.VectorField;

/**
 * Clearance-partitioned, poison-resistant semantic cache on Redis Stack / RediSearch (ADR-0036).
 *
 * <p><b>Structural RBAC invariant:</b> keys are {@code atlas:cache:<clearance>:<corpusVersion>:<uuid>} and
 * every KNN search carries a <em>mandatory</em> {@code @clearance:{<caller>} @corpus_version:{<ver>}}
 * pre-filter built from the <em>verified</em> caller clearance — so a lookup can only ever match within
 * the caller's own partition. A read-time {@code entry.clearance == caller} assertion is a second guard.
 * <b>Native TTL</b> via per-key EXPIRE; <b>conservative threshold</b> to resist collisions; writes are
 * trusted-write only (the caller is the Gateway, which caches only RBAC+guardrail+grounding-passed answers).
 */
public class RedisSemanticCache implements SemanticCache {

    private static final Logger log = LoggerFactory.getLogger(RedisSemanticCache.class);
    private static final String KEY_PREFIX = "atlas:cache:";
    private static final String SCORE_FIELD = "score";

    private final JedisPooled jedis;
    private final String indexName;
    private final int embeddingDim;
    private final double simThreshold;
    private final long ttlSeconds;
    private volatile boolean indexReady;

    public RedisSemanticCache(JedisPooled jedis, String indexName, int embeddingDim,
            double simThreshold, long ttlSeconds) {
        this.jedis = jedis;
        this.indexName = indexName;
        this.embeddingDim = embeddingDim;
        this.simThreshold = simThreshold;
        this.ttlSeconds = ttlSeconds;
    }

    @Override
    public Optional<CacheHit> lookup(String clearance, String corpusVersion, float[] queryVec) {
        if (queryVec == null || queryVec.length == 0) {
            return Optional.empty();
        }
        ensureIndex();
        // Mandatory clearance + corpus pre-filter → a cross-partition match is impossible by construction.
        String knn = "(@clearance:{" + clearance + "} @corpus_version:{" + corpusVersion + "})"
                + "=>[KNN 1 @embedding $vec AS " + SCORE_FIELD + "]";
        Query query = new Query(knn)
                .addParam("vec", Vectors.toBytes(queryVec))
                .returnFields("answer", "model", "clearance", SCORE_FIELD)
                .setSortBy(SCORE_FIELD, true)
                .limit(0, 1)
                .dialect(2);
        try {
            return topHit(jedis.ftSearch(indexName, query), clearance);
        } catch (JedisDataException e) {
            // Redis was flushed/restarted out from under us → the index is gone but our in-memory flag
            // said "ready". Recreate it and retry once before giving up (resilient to a Redis restart).
            if (isMissingIndex(e)) {
                synchronized (this) {
                    indexReady = false;
                }
                ensureIndex();
                try {
                    return topHit(jedis.ftSearch(indexName, query), clearance);
                } catch (JedisDataException retry) {
                    log.warn("Semantic cache lookup failed after index recreate ({}), treating as miss",
                            retry.getMessage());
                    return Optional.empty();
                }
            }
            log.warn("Semantic cache lookup failed ({}), treating as miss", e.getMessage());
            return Optional.empty();
        }
    }

    private Optional<CacheHit> topHit(SearchResult result, String clearance) {
        List<Document> docs = result.getDocuments();
        if (docs.isEmpty()) {
            return Optional.empty();
        }
        Document top = docs.get(0);
        // RediSearch COSINE returns distance = 1 - cosineSimilarity.
        double distance = parseDouble(top.getString(SCORE_FIELD));
        double similarity = 1.0 - distance;
        // Defense in depth: the structural filter guarantees this, assert it anyway.
        if (!clearance.equals(top.getString("clearance"))) {
            log.error("SECURITY: cache returned a cross-clearance entry — refusing the hit");
            return Optional.empty();
        }
        if (similarity < simThreshold) {
            return Optional.empty();
        }
        return Optional.of(new CacheHit(top.getString("answer"), top.getString("model"), similarity));
    }

    private static boolean isMissingIndex(JedisDataException e) {
        return e.getMessage() != null && e.getMessage().toLowerCase().contains("no such index");
    }

    @Override
    public void put(String clearance, String corpusVersion, float[] queryVec, CachedAnswer answer) {
        if (queryVec == null || queryVec.length == 0 || answer == null) {
            return;
        }
        ensureIndex();
        String key = KEY_PREFIX + clearance + ":" + corpusVersion + ":" + UUID.randomUUID();
        Map<byte[], byte[]> fields = new HashMap<>();
        fields.put(bytes("embedding"), Vectors.toBytes(queryVec));
        fields.put(bytes("clearance"), bytes(clearance));
        fields.put(bytes("corpus_version"), bytes(corpusVersion));
        fields.put(bytes("answer"), bytes(answer.answerJson() == null ? "" : answer.answerJson()));
        fields.put(bytes("model"), bytes(answer.model() == null ? "" : answer.model()));
        byte[] keyBytes = bytes(key);
        jedis.hset(keyBytes, fields);
        jedis.expire(keyBytes, ttlSeconds);
    }

    /** Idempotently create the RediSearch index (HNSW, COSINE) over the cache key prefix. */
    private void ensureIndex() {
        if (indexReady) {
            return;
        }
        synchronized (this) {
            if (indexReady) {
                return;
            }
            VectorField embedding = VectorField.builder()
                    .fieldName("embedding")
                    .algorithm(VectorField.VectorAlgorithm.HNSW)
                    .attributes(Map.of("TYPE", "FLOAT32", "DIM", embeddingDim, "DISTANCE_METRIC", "COSINE"))
                    .build();
            try {
                jedis.ftCreate(indexName,
                        FTCreateParams.createParams().on(IndexDataType.HASH).prefix(KEY_PREFIX),
                        new TagField("clearance"), new TagField("corpus_version"), embedding);
            } catch (JedisDataException e) {
                // "Index already exists" — fine; anything else rethrows.
                if (e.getMessage() == null || !e.getMessage().toLowerCase().contains("already exists")) {
                    throw e;
                }
            }
            indexReady = true;
        }
    }

    private static double parseDouble(String s) {
        try {
            return s == null ? 1.0 : Double.parseDouble(s);
        } catch (NumberFormatException e) {
            return 1.0; // treat unparseable distance as "far" → miss
        }
    }

    private static byte[] bytes(String s) {
        return s.getBytes(StandardCharsets.UTF_8);
    }
}
