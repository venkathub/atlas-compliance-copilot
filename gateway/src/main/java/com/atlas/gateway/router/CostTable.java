package com.atlas.gateway.router;

/**
 * The configured cost-units rate per tier (ADR-0040) + cost computation from token counts. "Cost-units"
 * are a synthetic-but-documented relative measure for self-hosted tiers and a real $-derived figure for
 * the frontier tier (CostProperties). Used by the cost meters (task 8) and the cost-delta report (task 10).
 */
public class CostTable {

    private final CostProperties props;

    public CostTable(CostProperties props) {
        this.props = props;
    }

    /** Cost-units per 1k tokens for {@code tier}. */
    public double unitsPer1k(ModelTier tier) {
        return switch (tier) {
            case TIER1_SMALL -> props.tier1UnitsPer1k();
            case TIER2_MID -> props.tier2UnitsPer1k();
            case TIER3_FRONTIER -> props.frontierUnitsPer1k();
        };
    }

    /** Cost-units for a request: {@code (promptTokens + completionTokens) / 1000 * unitsPer1k(tier)}. */
    public double costUnits(ModelTier tier, long promptTokens, long completionTokens) {
        long total = Math.max(0, promptTokens) + Math.max(0, completionTokens);
        return total / 1000.0 * unitsPer1k(tier);
    }
}
