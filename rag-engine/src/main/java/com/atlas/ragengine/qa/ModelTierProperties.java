package com.atlas.ragengine.qa;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Maps a Gateway-selected model tier (ADR-0035) to a chat-model override for rag-engine. Env-swappable;
 * no model name is hardcoded (CLAUDE.md). {@code tier1-small} uses the default {@link
 * org.springframework.ai.chat.model.ChatModel} (no override), so it is intentionally absent here.
 *
 * @param tier2Model       escalation model ({@code ATLAS_ROUTER_TIER2_MODEL})
 * @param frontierModel    reserved frontier model ({@code ATLAS_ROUTER_FRONTIER_MODEL}); off by default
 * @param frontierEnabled  whether the frontier tier may be served ({@code ATLAS_ROUTER_FRONTIER_ENABLED})
 * @param ftTierModel      served vLLM multi-LoRA adapter name for the fine-tuned citation tier (P7,
 *                         ADR-0080; {@code ATLAS_ROUTER_FT_TIER_MODEL}) — a model-name swap on the
 *                         single global vLLM backend, not an endpoint switch
 * @param ftTierEnabled    whether the FT tier may be served ({@code ATLAS_ROUTER_FT_TIER_ENABLED});
 *                         off by default (capability, served episodically)
 */
@ConfigurationProperties(prefix = "atlas.router")
public record ModelTierProperties(
        String tier2Model, String frontierModel, boolean frontierEnabled,
        String ftTierModel, boolean ftTierEnabled) {

    public ModelTierProperties {
        tier2Model = blankToNull(tier2Model);
        frontierModel = blankToNull(frontierModel);
        ftTierModel = blankToNull(ftTierModel);
    }

    private static String blankToNull(String v) {
        return (v == null || v.isBlank()) ? null : v;
    }
}
