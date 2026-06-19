package com.atlas.gateway.safety;

import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * PII egress redaction + output handling configuration (ADR-0037, OWASP LLM02/LLM05). Env-swappable.
 *
 * @param piiEnabled      master switch for the deterministic PII redactor ({@code ATLAS_PII_REDACTION_ENABLED})
 * @param sanitizeEnabled master switch for the output sanitizer ({@code ATLAS_OUTPUT_SANITIZE_ENABLED})
 * @param nameDenylist    literal restricted entities/names to redact ({@code ATLAS_PII_NAME_DENYLIST},
 *                        comma-separated) — a compliance-style denylist; NER breadth for unknown names is
 *                        the off-path Presidio deep-scan (ADR-0037, deferred). Never a secret in code.
 */
@ConfigurationProperties(prefix = "atlas.safety")
public record SafetyProperties(boolean piiEnabled, boolean sanitizeEnabled, List<String> nameDenylist) {

    public SafetyProperties {
        nameDenylist = nameDenylist == null ? List.of() : List.copyOf(nameDenylist);
    }
}
