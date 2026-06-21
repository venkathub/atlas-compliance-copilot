package com.atlas.mcptools.auth;

import org.springframework.stereotype.Component;

/**
 * Per-call authorization re-check at the tool (LLM06 / OWASP ASI03), independent of any upstream RBAC
 * (P1) or the resource-server token validation. Re-derives the caller's clearance from the validated
 * token and refuses to act below the configured minimum (default {@code compliance}). Refusal surfaces
 * as a {@link InsufficientClearanceException} → MCP error + a {@code DENIED} audit row (ADR-0046).
 */
@Component
public class ClearanceRecheck {

    private final Clearance required;

    public ClearanceRecheck(McpTokenProperties props) {
        this.required = Clearance.fromLabel(props.requiredClearance());
    }

    /** Refuse the call unless {@code clearanceLabel} is at least the required clearance. */
    public void require(String clearanceLabel) {
        Clearance actual;
        try {
            actual = Clearance.fromLabel(clearanceLabel);
        } catch (IllegalArgumentException e) {
            throw new InsufficientClearanceException("unknown clearance: " + clearanceLabel);
        }
        if (!actual.atLeast(required)) {
            throw new InsufficientClearanceException(
                    "caller clearance '" + actual.label() + "' is below required '" + required.label() + "'");
        }
    }
}
