import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { ReactElement } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { EvalScores } from "../src/app/admin/EvalScores.tsx";
import { CostDashboard } from "../src/app/admin/CostDashboard.tsx";
import { AuditLog } from "../src/app/admin/AuditLog.tsx";
import type { AuditPage, CostSummary, EvalSummary } from "../src/lib/types.ts";

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

const EVAL: EvalSummary = {
  generatedAt: "2026-06-27T10:33:02Z",
  gitSha: "da55199",
  rag: {
    passed: true,
    nSamples: 22,
    scores: {
      faithfulness: 0.7059,
      answerRelevancy: 0.8318,
      contextPrecision: 0.8258,
      contextRecall: 0.7379,
      citationCorrectness: 1.0,
    },
    adversarialPassRate: 1.0,
  },
  agent: {
    passed: true,
    scenarios: 12,
    taskSuccessRate: 1.0,
    toolSelectionRate: 1.0,
    hitlRespected: true,
    authorizationRespected: true,
    unapprovedWrites: 0,
    unauthorizedWrites: 0,
  },
};

const COST: CostSummary = {
  generatedAt: "2026-06-27T10:33:02Z",
  gitSha: "da55199",
  costReductionPct: 100.0,
  targetReductionPct: 30.0,
  meetsTarget: true,
  costOffUnits: 20.1096,
  costOnUnits: 0.0,
};

const AUDIT: AuditPage = {
  page: 0,
  size: 25,
  total: 1,
  chainVerified: true,
  rows: [
    {
      seq: 7,
      ts: "2026-06-27T10:00:00Z",
      runId: "run_abc123",
      tool: "open_draft_sar",
      phase: "SUCCESS",
      caller: "priya",
      clearance: "compliance",
      resultRef: "SAR-2026-000123",
    },
  ],
};

function withClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe("Admin · EvalScores", () => {
  it("renders RAG + agent scores with PASS badges from the committed summary", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, EVAL)));
    withClient(<EvalScores />);

    await waitFor(() => expect(screen.getByText(/RAG gate/i)).toBeInTheDocument());
    expect(screen.getByText(/Agent gate/i)).toBeInTheDocument();
    expect(screen.getAllByText("PASS")).toHaveLength(2);
    expect(screen.getByText("0.706")).toBeInTheDocument(); // faithfulness
  });

  it("degrades gracefully when the summary is unavailable (404)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(404, {})));
    withClient(<EvalScores />);
    await waitFor(() => expect(screen.getByText(/not available/i)).toBeInTheDocument());
  });
});

describe("Admin · CostDashboard", () => {
  it("shows the native cost-reduction headline and a Grafana fallback hint when URL unset", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, COST)));
    withClient(<CostDashboard />);
    await waitFor(() => expect(screen.getByText("100%")).toBeInTheDocument());
    // No VITE_GRAFANA_URL in test env → fallback hint, not an iframe.
    expect(screen.getByText(/VITE_GRAFANA_URL/)).toBeInTheDocument();
  });
});

describe("Admin · AuditLog", () => {
  it("renders rows from GET /v1/audit with a chain-verify badge", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, AUDIT)));
    withClient(<AuditLog />);

    await waitFor(() => expect(screen.getByText(/chain verified/i)).toBeInTheDocument());
    expect(screen.getByText("open_draft_sar")).toBeInTheDocument();
    expect(screen.getByText("SAR-2026-000123")).toBeInTheDocument();
  });

  it("paginates: Next advances the page query", async () => {
    const big = { ...AUDIT, total: 30 };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, big));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    withClient(<AuditLog />);

    await waitFor(() => expect(screen.getByText("Next")).toBeInTheDocument());
    await user.click(screen.getByText("Next"));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some((c) => String(c[0]).includes("page=1"))).toBe(true),
    );
  });
});
