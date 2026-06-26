/**
 * UI-facing TypeScript types — mirrors of the EXISTING backend HTTP contracts
 * (P5 spec §2.3). These are presentation-layer mirrors only: P1/P3/P4 own the
 * authoritative shapes and stay frozen. The browser only renders what these
 * trusted backends return; it never constructs a write or holds a secret.
 */

/**
 * Clearance levels (ascending). Mirrors the FROZEN sim-IdP / RBAC vocabulary
 * (gateway `Clearance` enum): public(0) < analyst(1) < compliance(2) < restricted(3).
 */
export type Clearance = "public" | "analyst" | "compliance" | "restricted";

// ── Login (POST /v1/auth/token, sim-IdP) ───────────────────────────────────
// NOTE: field names mirror the REAL frozen Gateway contract (SimIdpController),
// which differs from the spec §2.3 illustration: the request field is `user`
// (not `subject`), and the response also returns `tokenType` + `subject`.
export interface LoginRequest {
  user: string; // seeded identity: "priya" | "analyst-bob" | "guest-public" | "bsa-admin"
}

export interface LoginResponse {
  token: string;
  tokenType: string; // "Bearer"
  expiresIn: number; // seconds (default 3600)
  subject: string; // echoes the requested user id
  clearance: Clearance;
}

// ── RAG chat (POST /v1/query, P3 envelope) ─────────────────────────────────
// NOTE: field names mirror the REAL frozen Gateway contract (relays the rag-engine
// QueryResponse + adds routing/cache/redaction/cost sections), which differs from the
// spec §2.3 illustration: citation index is `marker` (not `n`); routing is
// {modelTier,model,escalated}; cost is {promptTokens,completionTokens,costUnits,latencyMs}.
export interface QueryRequest {
  query: string;
  topK?: number;
  includeContexts?: boolean;
}

export interface Citation {
  marker: number; // the [n] number
  documentId: string; // UUID
  docId?: string; // human slug, e.g. "l2-aml-policy-overview"
  title?: string;
  sourceUri?: string;
  chunkId?: string;
  clearance: Clearance;
  score?: number;
  snippet: string;
}

export interface Routing {
  modelTier: string; // e.g. "tier1-small" | "cache"
  model?: string; // concrete model id, e.g. "qwen2.5:3b-instruct"
  escalated?: boolean;
}

export interface Cache {
  hit: boolean;
  similarity?: number; // only present on a hit
}

export interface Cost {
  promptTokens: number;
  completionTokens: number;
  costUnits: number;
  latencyMs: number;
}

export interface RetrievalTrace {
  denseHits: number;
  sparseHits: number;
  fused: number;
  reranked: number;
  clearanceApplied: string;
}

export interface Redaction {
  applied: boolean;
  counts: Record<string, number>;
}

export interface QueryResponse {
  answer: string; // inline [n]-cited markdown — treated as UNTRUSTED at render (LLM05)
  citations: Citation[];
  retrieval?: RetrievalTrace;
  routing: Routing;
  cache: Cache;
  redaction?: Redaction;
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
