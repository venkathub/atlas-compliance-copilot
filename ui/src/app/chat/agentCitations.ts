import type { AgentCitation, Citation } from "../../lib/types.ts";

/**
 * Adapt agent-run citations (wire shape: `{n, documentId?, clearance?, snippet?}`) to
 * the shared render `Citation` shape (`marker` index). The agent and the gateway expose
 * different citation shapes; this keeps the `Answer`/`Citation` components reusable.
 */
export function adaptAgentCitations(citations: AgentCitation[] = []): Citation[] {
  return citations.map((c) => ({
    marker: c.n,
    documentId: c.documentId,
    clearance: c.clearance,
    snippet: c.snippet,
  }));
}
