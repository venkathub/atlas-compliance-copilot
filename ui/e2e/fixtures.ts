import type { Page, Route } from "@playwright/test";

/**
 * Deterministic backend fixtures + a route installer for the E2E gate. The UI talks to
 * its own origin (the proxy path-routes in prod); here we intercept those same paths and
 * pin the responses, so the gate never depends on a live model (§4.4).
 */

export const CLEARANCE_BY_USER: Record<string, string> = {
  priya: "compliance",
  "bsa-admin": "restricted",
  "analyst-bob": "analyst",
  "guest-public": "public",
};

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

export const AGENT_AWAITING = {
  runId: "run_e2e0001",
  status: "AWAITING_APPROVAL",
  answer: "3 open AML exceptions; **1 breaches the $10k threshold** [1].",
  citations: [
    { n: 1, documentId: "uuid-1", clearance: "compliance", snippet: "Wire of $12,400 flagged." },
  ],
  proposedAction: {
    tool: "open_draft_sar",
    args: { account: "Northwind", period: "2026-Q2", rationale: "threshold breach" },
  },
  trace: [
    { node: "retrieve", citations: 6 },
    { node: "assess", breach: true },
    { node: "approve" },
  ],
};

export const AGENT_COMPLETED = {
  runId: "run_e2e0001",
  status: "COMPLETED",
  answer: AGENT_AWAITING.answer,
  action: {
    tool: "open_draft_sar",
    draftRef: "SAR-2026-000123",
    status: "DRAFT",
    auditRef: "audit_42",
  },
  auditRef: "audit_42",
  trace: [...AGENT_AWAITING.trace, { node: "act_sar" }, { node: "finalize" }],
};

export const AUDIT_PAGE = {
  page: 0,
  size: 25,
  total: 1,
  chainVerified: true,
  rows: [
    {
      seq: 7,
      ts: "2026-06-27T10:00:00Z",
      runId: "run_e2e0001",
      tool: "open_draft_sar",
      phase: "SUCCESS",
      caller: "priya",
      clearance: "compliance",
      resultRef: "SAR-2026-000123",
    },
  ],
};

/** Build a plain RAG query response (used for the negative-access path). */
export function queryResponse(answer: string) {
  return {
    answer,
    citations: [],
    routing: { modelTier: "tier1-small", model: "qwen2.5:3b-instruct", escalated: false },
    cache: { hit: false },
    redaction: { applied: false, counts: {} },
    cost: { promptTokens: 400, completionTokens: 120, costUnits: 0.2, latencyMs: 900 },
  };
}

interface RouteOptions {
  /** AWAITING then COMPLETED for the agent run (the forcing story). */
  agent?: boolean;
  /** A pinned plain-query answer (the negative-access path). */
  queryAnswer?: string;
}

/** Install all backend route mocks for a test. Call BEFORE navigating. */
export async function installRoutes(page: Page, user: string, opts: RouteOptions = {}) {
  const clearance = CLEARANCE_BY_USER[user] ?? "public";

  await page.route("**/v1/auth/token", (route) =>
    json(route, 200, {
      token: `jwt-${user}`,
      tokenType: "Bearer",
      expiresIn: 3600,
      subject: user,
      clearance,
    }),
  );

  if (opts.agent) {
    await page.route("**/v1/agent/runs", (route) => json(route, 200, AGENT_AWAITING));
    await page.route("**/v1/agent/runs/*/resume", (route) => json(route, 200, AGENT_COMPLETED));
    await page.route("**/v1/agent/runs/run_e2e0001", (route) => json(route, 200, AGENT_AWAITING));
  }

  if (opts.queryAnswer !== undefined) {
    await page.route("**/v1/query", (route) => json(route, 200, queryResponse(opts.queryAnswer!)));
  }

  await page.route("**/v1/audit*", (route) => json(route, 200, AUDIT_PAGE));
}
