import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext.tsx";
import { ApiError } from "../../lib/apiClient.ts";
import type { Clearance } from "../../lib/types.ts";

/**
 * LoginPage — the sim-IdP identity picker (ADR-0003 sim-IdP; no real OIDC/SSO).
 *
 * The four seeded identities map one click → a clearance level, so the forcing
 * story (Priya/compliance) and the negative-access UX (sub-compliance) are each a
 * single click. Login posts `{ user }` to the FROZEN gateway `/v1/auth/token`.
 */

interface SeededIdentity {
  user: string; // the exact frozen sim-IdP subject string
  name: string;
  role: string;
  clearance: Clearance;
}

// Mirrors gateway dev/clearance-users.json (the only logins the sim-IdP accepts).
const IDENTITIES: SeededIdentity[] = [
  { user: "priya", name: "Priya", role: "Compliance Analyst", clearance: "compliance" },
  { user: "bsa-admin", name: "BSA Officer", role: "Admin", clearance: "restricted" },
  { user: "analyst-bob", name: "Bob", role: "Markets Analyst", clearance: "analyst" },
  { user: "guest-public", name: "Public Guest", role: "Unauthenticated tier", clearance: "public" },
];

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleLogin(user: string) {
    setError(null);
    setPending(user);
    try {
      await login(user);
      navigate("/chat", { replace: true });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Login failed (${err.status}).`
          : "Login failed. Is the gateway running?";
      setError(message);
    } finally {
      setPending(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <header className="text-center mb-6">
          <h1 className="text-2xl font-semibold">Atlas</h1>
          <p className="mt-1 text-sm text-slate-600">Enterprise AI operations copilot</p>
        </header>

        {/* AI-transparency note (full session-start disclosure lands in Task 3). */}
        <p className="mb-4 rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800">
          You are signing in to an <strong>AI system</strong>. Answers are AI-generated and any
          drafted action requires human review.
        </p>

        <section aria-labelledby="pick-identity">
          <h2 id="pick-identity" className="text-sm font-medium text-slate-700 mb-2">
            Choose a demo identity
          </h2>
          <ul className="space-y-2">
            {IDENTITIES.map((id) => (
              <li key={id.user}>
                <button
                  type="button"
                  onClick={() => handleLogin(id.user)}
                  disabled={pending !== null}
                  className="w-full text-left rounded-lg border border-slate-200 bg-white px-4 py-3 hover:border-slate-400 disabled:opacity-50 transition-colors"
                >
                  <span className="flex items-center justify-between">
                    <span>
                      <span className="font-medium">{id.name}</span>
                      <span className="text-slate-500"> — {id.role}</span>
                    </span>
                    <span className="text-xs uppercase tracking-wide text-slate-500">
                      {pending === id.user ? "signing in…" : id.clearance}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>

        {error && (
          <p role="alert" className="mt-4 text-sm text-red-700">
            {error}
          </p>
        )}
      </div>
    </main>
  );
}
