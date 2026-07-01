package com.atlas.gateway.router;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class ModelRouterTest {

    private static RoutingProperties props(boolean frontierEnabled) {
        return new RoutingProperties("tier1-small", "qwen2.5:3b-instruct", "qwen2.5:7b-instruct",
                1200, true, frontierEnabled, "gpt-4o", false, null);
    }

    private static RoutingProperties ftProps(boolean ftEnabled) {
        return new RoutingProperties("tier1-small", "qwen2.5:3b-instruct", "qwen2.5:7b-instruct",
                1200, true, false, "gpt-4o", ftEnabled, "atlas-citation-adapter");
    }

    private final ModelRouter router = new ModelRouter(props(false));

    @Test
    void defaultsToTier1Small() {
        ModelRouter.RoutingDecision d = router.route("short question", null);
        assertThat(d.tier()).isEqualTo(ModelTier.TIER1_SMALL);
        assertThat(d.model()).isEqualTo("qwen2.5:3b-instruct");
        assertThat(d.escalated()).isFalse();
    }

    @Test
    void qualityHighEscalatesToTier2() {
        ModelRouter.RoutingDecision d = router.route("anything", "high");
        assertThat(d.tier()).isEqualTo(ModelTier.TIER2_MID);
        assertThat(d.model()).isEqualTo("qwen2.5:7b-instruct");
        assertThat(d.escalated()).isTrue();
        assertThat(d.reason()).isEqualTo("quality=high");
    }

    @Test
    void longQueryEscalatesToTier2() {
        // > 1200 tokens ≈ > 4800 chars at ~4 chars/token.
        String big = "a".repeat(5000);
        ModelRouter.RoutingDecision d = router.route(big, null);
        assertThat(d.tier()).isEqualTo(ModelTier.TIER2_MID);
        assertThat(d.escalated()).isTrue();
        assertThat(d.reason()).contains("query_tokens>");
    }

    @Test
    void frontierIsNeverAutoSelectedEvenWhenEnabled() {
        ModelRouter enabledFrontier = new ModelRouter(props(true));
        // Strong escalation signal still tops out at tier2 — frontier is reserved/budget-gated.
        assertThat(enabledFrontier.route("a".repeat(9000), "high").tier()).isEqualTo(ModelTier.TIER2_MID);
    }

    @Test
    void evalFloorGuardFallsBackWhenConfiguredDefaultUnselectable() {
        // Configure default = frontier while frontier is disabled → must fall back to tier1-small.
        RoutingProperties p = new RoutingProperties("tier3-frontier", "qwen2.5:3b-instruct",
                "qwen2.5:7b-instruct", 1200, true, false, "gpt-4o", false, null);
        ModelRouter r = new ModelRouter(p);
        assertThat(r.route("short", null).tier()).isEqualTo(ModelTier.TIER1_SMALL);
    }

    @Test
    void ftTierSelectedWhenEnabledAndHinted() {
        ModelRouter r = new ModelRouter(ftProps(true));
        ModelRouter.RoutingDecision d = r.route("cite this", null, "true");
        assertThat(d.tier()).isEqualTo(ModelTier.TIER_FT_CITATION);
        assertThat(d.model()).isEqualTo("atlas-citation-adapter");
        assertThat(d.escalated()).isFalse(); // capability selection, not a cost escalation
        assertThat(d.reason()).isEqualTo("ft-hint");
    }

    @Test
    void ftTierNeverSelectedWhenFlagOffEvenWithHint() {
        ModelRouter r = new ModelRouter(ftProps(false));
        // Prod default: FT is not even selectable → the hint is ignored, falls through to default.
        assertThat(r.route("cite this", null, "true").tier()).isEqualTo(ModelTier.TIER1_SMALL);
    }

    @Test
    void ftTierNotAutoSelectedWithoutHint() {
        ModelRouter r = new ModelRouter(ftProps(true));
        // Enabled but no FT hint → never auto-selected; normal policy applies.
        assertThat(r.route("short", null, null).tier()).isEqualTo(ModelTier.TIER1_SMALL);
        assertThat(r.route("anything", "high", null).tier()).isEqualTo(ModelTier.TIER2_MID);
    }

    @Test
    void ftHintTakesPrecedenceOverQualityEscalation() {
        ModelRouter r = new ModelRouter(ftProps(true));
        // Both an FT hint and a strong escalation signal → FT wins (explicit capability request).
        assertThat(r.route("a".repeat(9000), "high", "citation").tier())
                .isEqualTo(ModelTier.TIER_FT_CITATION);
    }

    @Test
    void tokenEstimateIsDeterministic() {
        assertThat(ModelRouter.estimateTokens("12345678")).isEqualTo(2); // 8 chars / 4
        assertThat(ModelRouter.estimateTokens("")).isZero();
        assertThat(ModelRouter.estimateTokens(null)).isZero();
    }
}
