package com.atlas.ragengine.qa;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class ModelTierResolverTest {

    private static ModelTierResolver resolver(boolean frontierEnabled, String frontierModel) {
        return new ModelTierResolver(new ModelTierProperties("qwen2.5:7b-instruct", frontierModel, frontierEnabled));
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
}
