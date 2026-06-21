package com.atlas.mcptools.tool;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Source of the calling identity (subject + clearance) for a governed tool invocation.
 *
 * <p>This is a seam: in P4 task 3 the default implementation returns a configured identity so the
 * write + audit path is exercisable without auth. In <b>task 4</b> an OAuth 2.1 resource-server
 * implementation derives the caller + clearance from the validated (RFC 8707) Bearer token and adds
 * the per-call clearance re-check (refuse {@code < compliance}); it is registered as the primary
 * bean and supersedes this default.
 */
public interface ToolCallerContext {

    /** Identity of the current tool caller. */
    record CallerIdentity(String caller, String clearance) {}

    /** Resolve the caller for the in-flight invocation. */
    CallerIdentity current();

    /**
     * Default (task-3) implementation: a configured, fixed identity. In task 4 the token-backed
     * resource-server context is registered as {@code @Primary} and supersedes this for injection.
     */
    @Component
    class Default implements ToolCallerContext {

        private final String caller;
        private final String clearance;

        public Default(
                @Value("${atlas.mcp.default-caller:agent}") String caller,
                @Value("${atlas.mcp.default-clearance:compliance}") String clearance) {
            this.caller = caller;
            this.clearance = clearance;
        }

        @Override
        public CallerIdentity current() {
            return new CallerIdentity(caller, clearance);
        }
    }
}
