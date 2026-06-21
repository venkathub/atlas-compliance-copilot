package com.atlas.mcptools.tool;

/**
 * Structured output of {@code open_draft_sar} (P4_SPEC §2.3). Returning a record (rather than free
 * text) makes the MCP tool emit structured content the agent can consume directly.
 *
 * @param draftRef  human-facing reference, e.g. {@code SAR-2026-000123}
 * @param status    always {@code DRAFT} on creation (never auto-filed)
 * @param createdAt ISO-8601 creation timestamp
 */
public record OpenDraftSarResult(String draftRef, String status, String createdAt) {
}
