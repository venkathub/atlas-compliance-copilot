import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AgentRunView } from "../src/app/chat/AgentRunView.tsx";
import type { AgentRun } from "../src/lib/types.ts";

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

const AWAITING: AgentRun = {
  runId: "run_abc123",
  status: "AWAITING_APPROVAL",
  answer: "3 open AML exceptions; 1 breaches the $10k threshold [1].",
  citations: [{ n: 1, documentId: "uuid-1", clearance: "compliance", snippet: "Wire $12,400." }],
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

const COMPLETED: AgentRun = {
  runId: "run_abc123",
  status: "COMPLETED",
  answer: AWAITING.answer,
  action: {
    tool: "open_draft_sar",
    draftRef: "SAR-2026-000123",
    status: "DRAFT",
    auditRef: "audit_9",
  },
  auditRef: "audit_9",
  trace: [...(AWAITING.trace ?? []), { node: "act_sar" }, { node: "finalize" }],
};

const REJECTED: AgentRun = {
  runId: "run_abc123",
  status: "REJECTED",
  answer: AWAITING.answer,
  trace: [...(AWAITING.trace ?? []), { node: "rejected" }],
};

function renderRun() {
  return render(<AgentRunView query="aml exceptions?" account="Northwind" period="2026-Q2" />);
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal(
    "matchMedia",
    vi
      .fn()
      .mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  );
});
afterEach(() => vi.unstubAllGlobals());

describe("AgentRunView — HITL surface", () => {
  it("starts a run and renders the ApprovalCard with the proposed action + review stamp", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, AWAITING));
    vi.stubGlobal("fetch", fetchMock);
    renderRun();

    await waitFor(() => expect(screen.getByText(/Approval required/i)).toBeInTheDocument());
    expect(screen.getByText(/requires human review/i)).toBeInTheDocument();
    expect(screen.getByText("open_draft_sar")).toBeInTheDocument();
    // Start call posts {query,account,period} to /v1/agent/runs.
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/v1/agent/runs");
    expect(JSON.parse(init.body)).toEqual({
      query: "aml exceptions?",
      account: "Northwind",
      period: "2026-Q2",
    });
  });

  it("Approve forwards {approved:true} to resume and shows the draft SAR ref", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, AWAITING)) // start
      .mockResolvedValueOnce(jsonResponse(200, COMPLETED)); // resume
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderRun();

    await waitFor(() => expect(screen.getByText("Approve")).toBeInTheDocument());
    await user.click(screen.getByText("Approve"));

    await waitFor(() => expect(screen.getByTestId("draft-result")).toBeInTheDocument());
    expect(screen.getByTestId("draft-result")).toHaveTextContent("SAR-2026-000123");

    const [resumeUrl, resumeInit] = fetchMock.mock.calls[1];
    expect(resumeUrl).toContain("/v1/agent/runs/run_abc123/resume");
    expect(JSON.parse(resumeInit.body)).toMatchObject({ approved: true });
  });

  it("Reject forwards {approved:false}, shows no draftRef, and never fabricates a write", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, AWAITING)) // start
      .mockResolvedValueOnce(jsonResponse(200, REJECTED)); // resume
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderRun();

    await waitFor(() => expect(screen.getByText("Reject")).toBeInTheDocument());
    await user.click(screen.getByText("Reject"));

    await waitFor(() => expect(screen.getByText(/no draft was created/i)).toBeInTheDocument());
    expect(screen.queryByTestId("draft-result")).not.toBeInTheDocument();

    // Invariant: the ONLY calls are start + resume; the UI never POSTs to a tool/MCP
    // path and never invents a draftRef.
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls[0]).toContain("/v1/agent/runs");
    expect(urls[1]).toContain("/resume");
    expect(urls.some((u) => /mcp|open_draft_sar|\/tool/i.test(u))).toBe(false);
    const [, resumeInit] = fetchMock.mock.calls[1];
    expect(JSON.parse(resumeInit.body)).toMatchObject({ approved: false });
  });

  it("renders the collapsible execution trace", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, AWAITING)));
    const user = userEvent.setup();
    renderRun();

    await waitFor(() => expect(screen.getByText(/Execution trace/i)).toBeInTheDocument());
    await user.click(screen.getByText(/Execution trace/i));
    const steps = screen.getByTestId("trace-steps");
    expect(steps).toHaveTextContent("retrieve");
    expect(steps).toHaveTextContent("assess");
    expect(steps).toHaveTextContent("breach");
  });
});
