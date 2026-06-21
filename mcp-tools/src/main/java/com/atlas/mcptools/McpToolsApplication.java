package com.atlas.mcptools;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Atlas governed MCP Tool Server — the Java/Spring "moat" of P4 (ADR-0043 / D-P4-3).
 *
 * <p>Exposes governed enterprise actions over <b>MCP Streamable HTTP</b> (Spring AI MCP server on
 * WebMVC; MCP spec {@code 2025-11-25}). P4 task 1 stands up the module skeleton only: an MCP server
 * application exposing actuator health + Prometheus metrics, with <b>no tools registered yet</b>.
 *
 * <p>Subsequent P4 tasks layer on: the append-only hash-chained audit log (task 2), the
 * {@code open_draft_sar} governed write tool + {@code sar_draft} table (task 3), the OAuth 2.1 resource
 * server + per-call clearance re-check (task 4), and resource-scoped (RFC 8707) token validation (task 5).
 */
@SpringBootApplication
public class McpToolsApplication {

    public static void main(String[] args) {
        SpringApplication.run(McpToolsApplication.class, args);
    }
}
