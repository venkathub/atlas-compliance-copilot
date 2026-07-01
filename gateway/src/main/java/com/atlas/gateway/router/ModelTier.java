package com.atlas.gateway.router;

import java.util.Locale;

/** The model-tier catalog (P3_SPEC §2.3). Wire/label form is the lowercase {@link #label()}. */
public enum ModelTier {

    TIER1_SMALL("tier1-small"),
    TIER2_MID("tier2-mid"),
    TIER3_FRONTIER("tier3-frontier"),
    /** Fine-tuned citation/refusal adapter served via vLLM multi-LoRA (P7, ADR-0080). Flag-gated,
     * never auto-selected — reachable only via an explicit FT hint when {@code ft-tier-enabled}. */
    TIER_FT_CITATION("tier-ft-citation");

    private final String label;

    ModelTier(String label) {
        this.label = label;
    }

    public String label() {
        return label;
    }

    public static ModelTier fromLabel(String label) {
        if (label != null) {
            String norm = label.strip().toLowerCase(Locale.ROOT);
            for (ModelTier t : values()) {
                if (t.label.equals(norm)) {
                    return t;
                }
            }
        }
        throw new IllegalArgumentException("unknown model tier: " + label);
    }
}
