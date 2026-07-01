package com.atlas.gateway.router;

import java.util.EnumSet;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Cost-aware model router (ADR-0035). Deterministic, declarative, dashboard-friendly.
 *
 * <p>Defaults to the small/quantized tier (ADR-0005) and escalates to tier2-mid only on explicit
 * <em>pre-call</em> signals the Gateway can see before calling rag-engine: an estimated query-token
 * count over the configured threshold, or an explicit {@code X-Atlas-Quality: high} hint. Guarantees:
 * <ul>
 *   <li><b>default = tier1-small</b> when no signal fires;</li>
 *   <li><b>never_below_eval_floor</b> (R2): only eval-approved/selectable tiers can be chosen — the
 *       frontier tier is reserved/budget-gated and is <b>never auto-selected</b> (and not selectable
 *       at all unless {@code frontier-enabled});</li>
 *   <li>escalation tops out at tier2-mid (an eval-passing model).</li>
 * </ul>
 *
 * <p><b>Deferred (ADR-0035 note / §6.1):</b> the model-cascade (escalate when the tier-1 answer fails
 * the inline fact-check) and the {@code retrieved_context_tokens} rule are post-generation signals that
 * need a rag-engine confidence/context signal in the response — a follow-up, not this commit.
 */
@Component
public class ModelRouter {

    /** Quality hint header that requests escalation. */
    public static final String QUALITY_HEADER = "X-Atlas-Quality";

    /**
     * Explicit fine-tuned-tier request header (P7, ADR-0080). The FT citation tier is a proven
     * <em>capability</em>, not a prod default: it is selected only when {@code ft-tier-enabled} AND
     * this hint is truthy — never auto-selected. Distinct from the {@code X-Atlas-Model-Tier}
     * response header the Gateway forwards to rag-engine.
     */
    public static final String FT_HINT_HEADER = "X-Atlas-FT-Citation";

    private static final Logger log = LoggerFactory.getLogger(ModelRouter.class);

    private final RoutingProperties props;
    private final Set<ModelTier> selectable;
    private final ModelTier defaultTier;

    public ModelRouter(RoutingProperties props) {
        this.props = props;
        // Eval-approved/selectable set: the self-hosted tiers are eval-passing (verified in task 10);
        // the frontier tier is selectable only when explicitly enabled.
        EnumSet<ModelTier> s = EnumSet.of(ModelTier.TIER1_SMALL, ModelTier.TIER2_MID);
        if (props.frontierEnabled()) {
            s.add(ModelTier.TIER3_FRONTIER);
        }
        // The fine-tuned citation tier is selectable only when explicitly enabled (capability, not
        // an SLA — it is served episodically via vLLM multi-LoRA). Still never auto-selected: route()
        // picks it only on an explicit FT hint (ADR-0080).
        if (props.ftTierEnabled()) {
            s.add(ModelTier.TIER_FT_CITATION);
        }
        this.selectable = s;
        ModelTier configured = ModelTier.fromLabel(props.defaultTier());
        this.defaultTier = selectable.contains(configured) ? configured : ModelTier.TIER1_SMALL;
    }

    /** The router decision: the chosen tier, its model name, whether we escalated, and why. */
    public record RoutingDecision(ModelTier tier, String model, boolean escalated, String reason) {
    }

    /**
     * Route a request from its pre-call signals (2-arg overload: no FT hint).
     *
     * @param query       the user query (used to estimate size)
     * @param qualityHint value of {@link #QUALITY_HEADER} (nullable)
     */
    public RoutingDecision route(String query, String qualityHint) {
        return route(query, qualityHint, null);
    }

    /**
     * Route a request from its pre-call signals.
     *
     * <p>Order of precedence: an explicit, enabled FT hint wins (capability selection, not a cost
     * escalation); otherwise the cost-escalation policy (quality hint / big query → tier2). The FT
     * tier is <b>never</b> chosen without both {@code ft-tier-enabled} and a truthy hint (ADR-0080).
     *
     * @param query       the user query (used to estimate size)
     * @param qualityHint value of {@link #QUALITY_HEADER} (nullable)
     * @param ftHint      value of {@link #FT_HINT_HEADER} (nullable) requesting the fine-tuned tier
     */
    public RoutingDecision route(String query, String qualityHint, String ftHint) {
        if (wantsFt(ftHint) && selectable.contains(ModelTier.TIER_FT_CITATION)) {
            log.debug("Routing to tier-ft-citation (explicit FT hint, model {})", props.ftTierModel());
            return new RoutingDecision(ModelTier.TIER_FT_CITATION, props.ftTierModel(), false, "ft-hint");
        }

        int queryTokens = estimateTokens(query);
        boolean wantsHigh = qualityHint != null && qualityHint.strip().equalsIgnoreCase("high");
        boolean bigQuery = queryTokens > props.escalateQueryTokens();

        if ((wantsHigh || bigQuery) && selectable.contains(ModelTier.TIER2_MID)) {
            String reason = wantsHigh ? "quality=high" : ("query_tokens>" + props.escalateQueryTokens());
            log.debug("Routing to tier2-mid ({}, est {} query tokens)", reason, queryTokens);
            return new RoutingDecision(ModelTier.TIER2_MID, props.tier2Model(), true, reason);
        }
        return new RoutingDecision(defaultTier, modelFor(defaultTier), false, "default");
    }

    /** A truthy FT hint requests the fine-tuned citation tier. */
    private static boolean wantsFt(String ftHint) {
        if (ftHint == null) {
            return false;
        }
        String v = ftHint.strip().toLowerCase(java.util.Locale.ROOT);
        return v.equals("true") || v.equals("1") || v.equals("citation") || v.equals("ft");
    }

    private String modelFor(ModelTier tier) {
        return switch (tier) {
            case TIER1_SMALL -> props.tier1Model();
            case TIER2_MID -> props.tier2Model();
            case TIER3_FRONTIER -> props.frontierModel();
            case TIER_FT_CITATION -> props.ftTierModel();
        };
    }

    /** Deterministic, model-free token estimate (~4 chars/token) — stable for CI. */
    static int estimateTokens(String text) {
        if (text == null || text.isBlank()) {
            return 0;
        }
        return (int) Math.ceil(text.strip().length() / 4.0);
    }
}
