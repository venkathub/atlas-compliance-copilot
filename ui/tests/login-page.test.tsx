import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../src/app/auth/AuthContext.tsx";
import { LoginPage } from "../src/app/auth/LoginPage.tsx";

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

function renderLogin() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/login"]}>
        <LoginPage />
      </MemoryRouter>
    </AuthProvider>,
  );
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe("LoginPage", () => {
  it("renders all four seeded identities", () => {
    renderLogin();
    expect(screen.getByRole("button", { name: /Priya/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /BSA Officer/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Bob/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Public Guest/ })).toBeInTheDocument();
  });

  it("surfaces the AI-system disclosure", () => {
    renderLogin();
    expect(screen.getByText(/AI system/i)).toBeInTheDocument();
  });

  it("clicking Priya posts { user: 'priya' } to the sim-IdP", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        token: "t",
        tokenType: "Bearer",
        expiresIn: 3600,
        subject: "priya",
        clearance: "compliance",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("button", { name: /Priya/ }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/v1/auth/token");
    expect(JSON.parse(init.body)).toEqual({ user: "priya" });
  });

  it("shows an error message when login fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(400, { error: "unknown user" })));
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("button", { name: /Priya/ }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent(/login failed/i);
  });
});
