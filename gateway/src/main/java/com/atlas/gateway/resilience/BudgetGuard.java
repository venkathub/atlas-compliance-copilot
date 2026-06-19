package com.atlas.gateway.resilience;

/**
 * Per-user daily spend cap in cost-units (ADR-0038, LLM10). Two phases: a pre-request {@link #wouldExceed}
 * check (reject before spending), and post-request {@link #record} accounting of the actual cost.
 */
public interface BudgetGuard {

    /** @return true if charging {@code estimatedCost} would push the caller over their daily cap (→ 402). */
    boolean wouldExceed(String user, double estimatedCost);

    /** Add {@code actualCost} to the caller's accumulated spend for today. */
    void record(String user, double actualCost);
}
