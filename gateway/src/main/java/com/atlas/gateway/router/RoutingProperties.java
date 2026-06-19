package com.atlas.gateway.router;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Cost-aware model router configuration (ADR-0035). Declarative, env-swappable, never hardcoded.
 *
 * <p>The router defaults to the small/quantized tier (ADR-0005) and escalates only by explicit policy
 * signals the Gateway can see <em>before</em> calling rag-engine (query size, an explicit quality hint).
 * The frontier tier is budget-gated and reserved (never auto-selected). The model-cascade and the
 * {@code retrieved_context_tokens} rule are post-generation signals deferred to a follow-up (see
 * ADR-0035 implementation note / P3_SPEC §6.1).
 *
 * @param defaultTier          starting tier label ({@code ATLAS_ROUTER_DEFAULT_TIER})
 * @param tier1Model           display name of the default tier model (= {@code OLLAMA_CHAT_MODEL})
 * @param tier2Model           escalation model name ({@code ATLAS_ROUTER_TIER2_MODEL})
 * @param escalateQueryTokens  query-token threshold above which we escalate to tier2
 * @param cascadeEnabled       model-cascade flag (reserved; not yet wired — see note)
 * @param frontierEnabled      whether the frontier tier may be served ({@code ATLAS_ROUTER_FRONTIER_ENABLED})
 * @param frontierModel        reserved frontier model name ({@code ATLAS_ROUTER_FRONTIER_MODEL})
 */
@ConfigurationProperties(prefix = "atlas.router")
public record RoutingProperties(
        String defaultTier,
        String tier1Model,
        String tier2Model,
        int escalateQueryTokens,
        boolean cascadeEnabled,
        boolean frontierEnabled,
        String frontierModel) {

    public RoutingProperties {
        defaultTier = blankTo(defaultTier, ModelTier.TIER1_SMALL.label());
        tier1Model = blankTo(tier1Model, "qwen2.5:3b-instruct");
        tier2Model = blankTo(tier2Model, "qwen2.5:7b-instruct");
        escalateQueryTokens = escalateQueryTokens > 0 ? escalateQueryTokens : 1200;
        frontierModel = (frontierModel == null || frontierModel.isBlank()) ? null : frontierModel;
    }

    private static String blankTo(String v, String fallback) {
        return (v == null || v.isBlank()) ? fallback : v;
    }
}
