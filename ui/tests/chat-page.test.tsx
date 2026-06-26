import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChatPage } from "../src/app/chat/ChatPage.tsx";
import type { QueryResponse } from "../src/lib/types.ts";

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

const ANSWER: QueryResponse = {
  answer: "There are **3 open AML exceptions** [1].",
  citations: [
    {
      marker: 1,
      documentId: "uuid-1",
      docId: "l2-northwind-amlexc-q2",
      clearance: "compliance",
      snippet: "Exception over $10k.",
    },
  ],
  routing: { modelTier: "tier1-small", model: "qwen2.5:3b-instruct", escalated: false },
  cache: { hit: false },
  redaction: { applied: false, counts: {} },
  cost: { promptTokens: 800, completionTokens: 200, costUnits: 0.3, latencyMs: 1234 },
};

function renderChat() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ChatPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  // Reduced motion → progressive reveal is instant + deterministic (no timers).
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());

describe("ChatPage", () => {
  it("shows the session-start AI disclosure", () => {
    renderChat();
    expect(screen.getByRole("note")).toHaveTextContent(/AI system/i);
  });

  it("submits a query and renders the cited answer + AI label + meta badges", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, ANSWER));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderChat();

    await user.type(screen.getByLabelText("Ask a question"), "open AML exceptions?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(screen.getByText("AI-generated")).toBeInTheDocument());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/v1/query");
    expect(JSON.parse(init.body)).toEqual({ query: "open AML exceptions?" });

    await waitFor(() => expect(screen.getByText(/3 open AML exceptions/)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "[1]" })).toBeInTheDocument();
    expect(screen.getByTestId("meta-badges")).toHaveTextContent("cache: miss");
    expect(screen.getByTestId("meta-badges")).toHaveTextContent("tier1-small");
  });

  it("renders a friendly error on a 402 budget response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(402, { error: "daily budget exceeded" })),
    );
    const user = userEvent.setup();
    renderChat();

    await user.type(screen.getByLabelText("Ask a question"), "anything");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent(/budget exceeded/i);
  });
});
