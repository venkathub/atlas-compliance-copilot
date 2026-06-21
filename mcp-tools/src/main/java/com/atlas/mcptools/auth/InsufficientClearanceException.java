package com.atlas.mcptools.auth;

/** Raised when a tool caller's clearance is below the required minimum (LLM06). Maps to a DENIED audit. */
public class InsufficientClearanceException extends RuntimeException {
    public InsufficientClearanceException(String message) {
        super(message);
    }
}
