package com.atlas.gateway.router;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Cost-units table (ADR-0040). Synthetic per-1k cost-units for the self-hosted tiers (derived from
 * GPU ₹/hr ÷ throughput; documented estimates) and a real $-derived figure for the frontier tier.
 * Backs the Grafana cost dashboard (task 8) + the cost-delta report (task 10). Env-swappable.
 *
 * @param tier1UnitsPer1k cost-units per 1k tokens for tier1-small ({@code ATLAS_COST_TIER1_UNITS_PER_1K})
 * @param tier2UnitsPer1k cost-units per 1k tokens for tier2-mid ({@code ATLAS_COST_TIER2_UNITS_PER_1K})
 * @param frontierUnitsPer1k cost-units per 1k tokens for the frontier tier ({@code ATLAS_COST_FRONTIER_UNITS_PER_1K})
 * @param ftTierUnitsPer1k cost-units per 1k tokens for the fine-tuned citation tier (P7; same 7B
 *        family as tier2, so default matches tier2; {@code ATLAS_COST_FT_TIER_UNITS_PER_1K})
 */
@ConfigurationProperties(prefix = "atlas.cost")
public record CostProperties(
        double tier1UnitsPer1k, double tier2UnitsPer1k, double frontierUnitsPer1k, double ftTierUnitsPer1k) {

    public CostProperties {
        tier1UnitsPer1k = tier1UnitsPer1k > 0 ? tier1UnitsPer1k : 0.30;
        tier2UnitsPer1k = tier2UnitsPer1k > 0 ? tier2UnitsPer1k : 0.70;
        frontierUnitsPer1k = frontierUnitsPer1k > 0 ? frontierUnitsPer1k : 5.00;
        ftTierUnitsPer1k = ftTierUnitsPer1k > 0 ? ftTierUnitsPer1k : 0.70;
    }
}
