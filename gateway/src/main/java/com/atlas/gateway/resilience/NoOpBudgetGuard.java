package com.atlas.gateway.resilience;

/** No-op budget (never exceeds, records nothing) — wired when {@code atlas.resilience.budget-enabled=false}. */
public class NoOpBudgetGuard implements BudgetGuard {

    @Override
    public boolean wouldExceed(String user, double estimatedCost) {
        return false;
    }

    @Override
    public void record(String user, double actualCost) {
        // intentionally no-op
    }
}
