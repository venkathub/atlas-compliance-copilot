package com.atlas.gateway.resilience;

import java.time.LocalDate;
import java.time.ZoneOffset;
import redis.clients.jedis.JedisPooled;

/**
 * Redis-backed daily budget (ADR-0038, LLM10). Per-user accumulated cost-units live in
 * {@code atlas:budget:<user>:<yyyymmdd>} (UTC day), expiring after ~2 days. The pre-request check reads the
 * current spend; post-request accounting atomically increments it.
 */
public class RedisBudgetGuard implements BudgetGuard {

    private static final String KEY_PREFIX = "atlas:budget:";
    private static final long TTL_SECONDS = 172_800; // 2 days — outlives the UTC day boundary

    private final JedisPooled jedis;
    private final double dailyCapUnits;

    public RedisBudgetGuard(JedisPooled jedis, double dailyCapUnits) {
        this.jedis = jedis;
        this.dailyCapUnits = dailyCapUnits;
    }

    @Override
    public boolean wouldExceed(String user, double estimatedCost) {
        String current = jedis.get(key(user));
        double spent = current == null ? 0.0 : parse(current);
        return spent + Math.max(0, estimatedCost) > dailyCapUnits;
    }

    @Override
    public void record(String user, double actualCost) {
        if (actualCost <= 0) {
            return;
        }
        String key = key(user);
        jedis.incrByFloat(key, actualCost);
        jedis.expire(key, TTL_SECONDS);
    }

    private String key(String user) {
        return KEY_PREFIX + user + ":" + LocalDate.now(ZoneOffset.UTC).toString().replace("-", "");
    }

    private static double parse(String s) {
        try {
            return Double.parseDouble(s);
        } catch (NumberFormatException e) {
            return 0.0;
        }
    }
}
