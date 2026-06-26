/**
 * UI-facing TypeScript types — mirrors of the EXISTING backend HTTP contracts
 * (P5 spec §2.3). These are presentation-layer mirrors only: P1/P3/P4 own the
 * authoritative shapes and stay frozen. The browser only renders what these
 * trusted backends return; it never constructs a write or holds a secret.
 */

/** Clearance levels (ascending). Mirrors the sim-IdP / RBAC vocabulary. */
export type Clearance = "public" | "analyst" | "compliance";

// ── Login (POST /v1/auth/token, sim-IdP) ───────────────────────────────────
export interface LoginRequest {
  subject: string; // seeded identity, e.g. "priya" | "analyst" | "public"
}

export interface LoginResponse {
  token: string;
  clearance: Clearance;
  expiresIn: number; // seconds
}

// ── RAG chat (POST /v1/query, P3 envelope) ─────────────────────────────────
export interface Citation {
  n: number;
  documentId: string;
  clearance: Clearance;
  snippet: string;
}

export interface Routing {
  tier: string; // e.g. "TIER1_SMALL"
  cache: "hit" | "miss" | string;
}

export interface Cost {
  inputTokens: number;
  outputTokens: number;
  units: number;
}

export interface QueryResponse {
  answer: string; // inline [n]-cited markdown — treated as UNTRUSTED at render (LLM05)
  citations: Citation[];
  routing: Routing;
  cost: Cost;
}

// ── Agent run (POST /v1/agent/runs → resume, P4) ───────────────────────────
export type AgentRunStatus = "RUNNING" | "AWAITING_APPROVAL" | "COMPLETED" | "REJECTED" | "FAILED";

export interface ProposedAction {
  tool: string; // e.g. "open_draft_sar"
  args: Record<string, unknown>;
}

export interface TraceStep {
  node: string; // planner | retrieve | assess | approve | act
  ms?: number;
  [k: string]: unknown; // node-specific fields (e.g. breach:true)
}

export interface AgentAction {
  draftRef: string; // e.g. "SAR-2026-000123"
  status: string; // e.g. "DRAFT"
}

export interface AgentRun {
  runId: string;
  status: AgentRunStatus;
  answer?: string;
  citations?: Citation[];
  proposedAction?: ProposedAction;
  trace?: TraceStep[];
  action?: AgentAction;
  auditRef?: string;
}

export interface ResumeRequest {
  approved: boolean;
  note?: string;
}

// ── Audit read (GET /v1/audit, NEW read-only) ──────────────────────────────
export interface AuditRow {
  seq: number;
  ts: string;
  runId: string;
  tool: string;
  phase: string; // e.g. "SUCCESS" | "REJECTED"
  caller: string;
  clearance: Clearance;
  resultRef: string;
}

export interface AuditPage {
  page: number;
  size: number;
  total: number;
  chainVerified: boolean;
  rows: AuditRow[];
}

// ── Eval scores (committed gate artifact / Langfuse) ───────────────────────
export interface RagGate {
  faithfulness: number;
  answerRelevancy: number;
  contextRecall: number;
  passed: boolean;
}

export interface AgentGate {
  taskSuccess: number;
  of: number;
  toolCallCorrectness: number;
  hitlEnforced: boolean;
  passed: boolean;
}

export interface EvalScores {
  ragGate: RagGate;
  agentGate: AgentGate;
  generatedAt: string;
  commit: string;
}
