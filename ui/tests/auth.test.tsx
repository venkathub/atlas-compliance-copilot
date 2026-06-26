import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider, useAuth } from "../src/app/auth/AuthContext.tsx";
import { apiFetch, ApiError } from "../src/lib/apiClient.ts";

// ── fetch mock helpers ──────────────────────────────────────────────────────
function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

const PRIYA_LOGIN = {
  token: "jwt-priya-123",
  tokenType: "Bearer",
  expiresIn: 3600,
  subject: "priya",
  clearance: "compliance",
};

// A small consumer that surfaces auth state + actions for the test.
function Harness() {
  const { session, isAuthenticated, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="authed">{String(isAuthenticated)}</span>
      <span data-testid="subject">{session?.subject ?? "none"}</span>
      <span data-testid="clearance">{session?.clearance ?? "none"}</span>
      <button onClick={() => void login("priya")}>login</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

function renderHarness() {
  return render(
    <AuthProvider>
      <Harness />
    </AuthProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AuthContext", () => {
  it("login stores the in-memory session from the sim-IdP response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, PRIYA_LOGIN)));
    const user = userEvent.setup();
    renderHarness();

    expect(screen.getByTestId("authed")).toHaveTextContent("false");
    await user.click(screen.getByText("login"));

    await waitFor(() => expect(screen.getByTestId("authed")).toHaveTextContent("true"));
    expect(screen.getByTestId("subject")).toHaveTextContent("priya");
    expect(screen.getByTestId("clearance")).toHaveTextContent("compliance");
  });

  it("login posts { user } to /v1/auth/token (real frozen contract field name)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, PRIYA_LOGIN));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderHarness();

    await user.click(screen.getByText("login"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/v1/auth/token");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ user: "priya" });
  });

  it("attaches Authorization: Bearer <jwt> on a subsequent apiFetch after login", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, PRIYA_LOGIN)) // login
      .mockResolvedValueOnce(jsonResponse(200, { ok: true })); // later call
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderHarness();

    await user.click(screen.getByText("login"));
    await waitFor(() => expect(screen.getByTestId("authed")).toHaveTextContent("true"));

    await apiFetch("/v1/query", { method: "POST", body: { query: "hi" } });

    const [, init] = fetchMock.mock.calls[1];
    expect(init.headers["Authorization"]).toBe("Bearer jwt-priya-123");
  });

  it("logout clears the in-memory session", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, PRIYA_LOGIN)));
    const user = userEvent.setup();
    renderHarness();

    await user.click(screen.getByText("login"));
    await waitFor(() => expect(screen.getByTestId("authed")).toHaveTextContent("true"));

    await user.click(screen.getByText("logout"));
    expect(screen.getByTestId("authed")).toHaveTextContent("false");
    expect(screen.getByTestId("subject")).toHaveTextContent("none");
  });

  it("a 401 from any call clears the session (expiry/tamper → re-login)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, PRIYA_LOGIN)) // login
      .mockResolvedValueOnce(jsonResponse(401, { error: "unauthorized" })); // expired call
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderHarness();

    await user.click(screen.getByText("login"));
    await waitFor(() => expect(screen.getByTestId("authed")).toHaveTextContent("true"));

    // The 401 handler clears session via setState outside a React event — wrap in act.
    await act(async () => {
      await expect(apiFetch("/v1/query", { method: "POST", body: {} })).rejects.toBeInstanceOf(
        ApiError,
      );
    });
    expect(screen.getByTestId("authed")).toHaveTextContent("false");
  });
});
