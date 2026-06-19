package com.atlas.gateway.cache;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Optional;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import redis.clients.jedis.JedisPooled;

/**
 * Hard-gate ITs for the clearance-safe semantic cache (ADR-0036) against a real Redis Stack / RediSearch.
 * Model-free (stub vectors); needs Docker (not a GPU).
 *
 * <p>The headline is the <b>cross-clearance negative-cache gate</b> (R1): an answer cached at one clearance
 * is NEVER returned to a lower/other clearance, even at identical similarity — structurally impossible.
 */
@Testcontainers
class RedisSemanticCacheIT {

    private static final int DIM = 8;
    private static final double THRESHOLD = 0.95;

    @Container
    static final GenericContainer<?> REDIS =
            new GenericContainer<>(DockerImageName.parse(
                    "redis/redis-stack-server:7.4.0-v3"))
                    .withExposedPorts(6379);

    private static JedisPooled jedis;
    private RedisSemanticCache cache;

    @BeforeAll
    static void connect() {
        jedis = new JedisPooled(REDIS.getHost(), REDIS.getMappedPort(6379));
    }

    @AfterAll
    static void close() {
        jedis.close();
    }

    @BeforeEach
    void freshIndex() {
        jedis.flushAll(); // clears keys + the FT index; the cache recreates it lazily
        cache = new RedisSemanticCache(jedis, "atlas-cache-idx", DIM, THRESHOLD, 86_400);
    }

    private static float[] vec(float... v) {
        return v;
    }

    private static SemanticCache.CachedAnswer answer(String text) {
        return new SemanticCache.CachedAnswer("{\"answer\":\"" + text + "\"}", "qwen2.5:3b-instruct");
    }

    @Test
    void identicalQueryHitsWithinSameClearance() {
        float[] v = vec(1, 0, 0, 0, 0, 0, 0, 0);
        cache.put("compliance", "v1", v, answer("compliance secret"));

        Optional<SemanticCache.CacheHit> hit = cache.lookup("compliance", "v1", v);
        assertThat(hit).isPresent();
        assertThat(hit.get().similarity()).isGreaterThanOrEqualTo(THRESHOLD);
        assertThat(hit.get().answerJson()).contains("compliance secret");
    }

    @Test
    void crossClearanceNeverHits() {
        // ★ HARD GATE (R1): cache a compliance answer, then attempt to read it at every other clearance
        // with the IDENTICAL embedding. A cross-clearance hit must be structurally impossible.
        float[] v = vec(1, 0, 0, 0, 0, 0, 0, 0);
        cache.put("compliance", "v1", v, answer("restricted-ish compliance content"));

        assertThat(cache.lookup("public", "v1", v)).isEmpty();
        assertThat(cache.lookup("analyst", "v1", v)).isEmpty();
        assertThat(cache.lookup("restricted", "v1", v)).isEmpty();
        // sanity: the owning clearance still hits
        assertThat(cache.lookup("compliance", "v1", v)).isPresent();
    }

    @Test
    void belowThresholdNearMissDoesNotCollide() {
        // Stored at v=[1,0,..]; query at [1,1,0,..] → cosine ≈ 0.707 < 0.95 → must be a miss (no collision).
        cache.put("compliance", "v1", vec(1, 0, 0, 0, 0, 0, 0, 0), answer("a"));
        assertThat(cache.lookup("compliance", "v1", vec(1, 1, 0, 0, 0, 0, 0, 0))).isEmpty();
    }

    @Test
    void corpusVersionMismatchIsMiss() {
        float[] v = vec(0, 1, 0, 0, 0, 0, 0, 0);
        cache.put("compliance", "v1", v, answer("old corpus"));
        assertThat(cache.lookup("compliance", "v2", v)).isEmpty(); // re-ingest invalidation
        assertThat(cache.lookup("compliance", "v1", v)).isPresent();
    }

    @Test
    void entriesExpireWithTtl() throws Exception {
        RedisSemanticCache shortTtl = new RedisSemanticCache(jedis, "atlas-cache-idx", DIM, THRESHOLD, 1);
        float[] v = vec(0, 0, 1, 0, 0, 0, 0, 0);
        shortTtl.put("compliance", "v1", v, answer("ephemeral"));
        assertThat(shortTtl.lookup("compliance", "v1", v)).isPresent();
        Thread.sleep(1500);
        assertThat(shortTtl.lookup("compliance", "v1", v)).isEmpty();
    }

    @Test
    void recreatesIndexAfterRedisFlush() {
        // Regression: a Redis flush/restart drops the RediSearch index out from under a live cache whose
        // in-memory "indexReady" flag is still set. A subsequent lookup must transparently recreate it.
        float[] v = vec(1, 0, 0, 0, 0, 0, 0, 0);
        cache.put("compliance", "v1", v, answer("before flush"));
        assertThat(cache.lookup("compliance", "v1", v)).isPresent();

        jedis.flushAll(); // drops keys AND the FT index, simulating a Redis restart

        cache.put("compliance", "v1", v, answer("after flush"));
        assertThat(cache.lookup("compliance", "v1", v)).isPresent(); // index auto-recreated, hit served
    }
}
