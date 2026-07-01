package com.atlas.gateway.router;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

import org.junit.jupiter.api.Test;

class CostTableTest {

    private final CostTable costs = new CostTable(new CostProperties(0.30, 0.70, 5.00, 0.70));

    @Test
    void unitsPerTier() {
        assertThat(costs.unitsPer1k(ModelTier.TIER1_SMALL)).isEqualTo(0.30);
        assertThat(costs.unitsPer1k(ModelTier.TIER2_MID)).isEqualTo(0.70);
        assertThat(costs.unitsPer1k(ModelTier.TIER3_FRONTIER)).isEqualTo(5.00);
        assertThat(costs.unitsPer1k(ModelTier.TIER_FT_CITATION)).isEqualTo(0.70);
    }

    @Test
    void costFromTokens() {
        // 1000 prompt + 1000 completion = 2000 tokens; tier1 @0.30/1k → 0.60 units.
        assertThat(costs.costUnits(ModelTier.TIER1_SMALL, 1000, 1000)).isCloseTo(0.60, within(1e-9));
        // tier2 @0.70/1k for 500+500=1000 → 0.70.
        assertThat(costs.costUnits(ModelTier.TIER2_MID, 500, 500)).isCloseTo(0.70, within(1e-9));
    }

    @Test
    void negativeTokensClampToZero() {
        assertThat(costs.costUnits(ModelTier.TIER1_SMALL, -5, -5)).isZero();
    }
}
