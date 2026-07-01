package com.atlas.ragengine.qa;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class ModelTierResolverTest {

    private static ModelTierResolver resolver(boolean frontierEnabled, String frontierModel) {
        return new ModelTierResolver(
                new ModelTierProperties("qwen2.5:7b-instruct", frontierModel, frontierEnabled, null, false));
    }

    private static ModelTierResolver ftResolver(boolean ftEnabled, String ftModel) {
        return new ModelTierResolver(
                new ModelTierProperties("qwen2.5:7b-instruct", null, false, ftModel, ftEnabled));
    }

    @Test
    void tier1AndAbsentAndUnknownUseDefaultModel() {
        ModelTierResolver r = resolver(false, null);
        assertThat(r.resolveModel("tier1-small")).isEmpty();
        assertThat(r.resolveModel(null)).isEmpty();
        assertThat(r.resolveModel("")).isEmpty();
        assertThat(r.resolveModel("bogus-tier")).isEmpty();
    }

    @Test
    void tier2MapsToEscalationModel() {
        assertThat(resolver(false, null).resolveModel("tier2-mid")).contains("qwen2.5:7b-instruct");
        assertThat(resolver(false, null).resolveModel("TIER2-MID")).contains("qwen2.5:7b-instruct"); // case-insensitive
    }

    @Test
    void frontierResolvesOnlyWhenEnabledAndConfigured() {
        assertThat(resolver(true, "gpt-4o").resolveModel("tier3-frontier")).contains("gpt-4o");
        assertThat(resolver(false, "gpt-4o").resolveModel("tier3-frontier")).isEmpty(); // disabled → default
        assertThat(resolver(true, null).resolveModel("tier3-frontier")).isEmpty();      // unconfigured → default
    }

    @Test
    void ftCitationResolvesOnlyWhenEnabledAndConfigured() {
        // enabled + configured → the served vLLM LoRA model-name (ADR-0080)
        assertThat(ftResolver(true, "atlas-citation-adapter").resolveModel("tier-ft-citation"))
                .contains("atlas-citation-adapter");
        // case-insensitive
        assertThat(ftResolver(true, "atlas-citation-adapter").resolveModel("TIER-FT-CITATION"))
                .contains("atlas-citation-adapter");
        // disabled → fail-safe to default ChatModel
        assertThat(ftResolver(false, "atlas-citation-adapter").resolveModel("tier-ft-citation")).isEmpty();
        // unconfigured → fail-safe to default ChatModel
        assertThat(ftResolver(true, null).resolveModel("tier-ft-citation")).isEmpty();
    }
}
