package com.atlas.ragengine.qa;

import java.util.Locale;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Resolves a Gateway-selected model tier (header {@link #HEADER}) to a per-request chat-model override
 * (P3 model router, ADR-0035). The Gateway owns the routing <em>decision</em>; rag-engine owns model
 * serving (Spring AI) and only maps the tier → a concrete model name.
 *
 * <ul>
 *   <li>{@code tier1-small} (or absent/unknown) → {@link Optional#empty()} = use the default ChatModel
 *       (the small/quantized RAG model, ADR-0005) — fail-safe to the cheapest eval-passing tier;</li>
 *   <li>{@code tier2-mid} → the configured escalation model;</li>
 *   <li>{@code tier3-frontier} → the frontier model, but only when explicitly enabled (else fail-safe
 *       to default).</li>
 *   <li>{@code tier-ft-citation} → the fine-tuned adapter served on the global vLLM multi-LoRA
 *       backend, but only when explicitly enabled + configured (else fail-safe to default). This is a
 *       model-name swap on the single backend, not an endpoint switch (P7, ADR-0080).</li>
 * </ul>
 */
public class ModelTierResolver {

    /** Header the Gateway uses to convey the selected tier. */
    public static final String HEADER = "X-Atlas-Model-Tier";

    public static final String TIER1_SMALL = "tier1-small";
    public static final String TIER2_MID = "tier2-mid";
    public static final String TIER3_FRONTIER = "tier3-frontier";
    public static final String TIER_FT_CITATION = "tier-ft-citation";

    private static final Logger log = LoggerFactory.getLogger(ModelTierResolver.class);

    private final ModelTierProperties props;

    public ModelTierResolver(ModelTierProperties props) {
        this.props = props;
    }

    /**
     * @param tier the Gateway-selected tier label (nullable)
     * @return the model name to override with, or empty to use the default ChatModel
     */
    public Optional<String> resolveModel(String tier) {
        if (tier == null || tier.isBlank()) {
            return Optional.empty();
        }
        String normalized = tier.strip().toLowerCase(Locale.ROOT);
        return switch (normalized) {
            case TIER1_SMALL -> Optional.empty();
            case TIER2_MID -> Optional.ofNullable(props.tier2Model());
            case TIER3_FRONTIER -> {
                if (props.frontierEnabled() && props.frontierModel() != null) {
                    yield Optional.of(props.frontierModel());
                }
                log.warn("Frontier tier requested but disabled/unconfigured — using default model");
                yield Optional.empty();
            }
            case TIER_FT_CITATION -> {
                if (props.ftTierEnabled() && props.ftTierModel() != null) {
                    yield Optional.of(props.ftTierModel());
                }
                log.warn("FT citation tier requested but disabled/unconfigured — using default model");
                yield Optional.empty();
            }
            default -> {
                log.warn("Unknown model tier '{}' — using default model", tier);
                yield Optional.empty();
            }
        };
    }
}
