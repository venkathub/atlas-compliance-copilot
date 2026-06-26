import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { apiFetch, setTokenProvider, setUnauthorizedHandler } from "../../lib/apiClient.ts";
import type { Clearance, LoginRequest, LoginResponse } from "../../lib/types.ts";

/**
 * AuthContext — the in-memory session (D-P5-6 / ADR for token storage).
 *
 * The JWT lives ONLY in React state: not in localStorage (XSS-exfiltratable) and
 * not in a cookie (no BFF session in the sim-IdP). A page refresh drops it and the
 * user re-logs-in — acceptable, since sim-IdP login is one click. The sim-IdP returns
 * the verified `clearance` + `subject` in the response body, so the UI needs NO
 * client-side JWT decoding (smaller attack surface); clearance is used only to gate
 * which tabs render and is ALWAYS re-enforced server-side.
 */

export interface Session {
  token: string;
  subject: string;
  clearance: Clearance;
}

interface AuthContextValue {
  session: Session | null;
  isAuthenticated: boolean;
  login: (user: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);

  // Mirror the latest token into a ref so the apiClient token provider (registered
  // once) always reads the current value without re-registering each render. The ref
  // is updated in an effect (never during render).
  const tokenRef = useRef<string | null>(null);
  useEffect(() => {
    tokenRef.current = session?.token ?? null;
  }, [session]);

  const logout = useCallback(() => {
    setSession(null);
  }, []);

  const login = useCallback(async (user: string) => {
    const body: LoginRequest = { user };
    const res = await apiFetch<LoginResponse>("/v1/auth/token", {
      method: "POST",
      body,
    });
    setSession({ token: res.token, subject: res.subject, clearance: res.clearance });
  }, []);

  // Register the apiClient seams exactly once: how it reads the Bearer token, and
  // what to do on a 401 (expiry/tamper) — clear the in-memory session → routes to login.
  useEffect(() => {
    setTokenProvider(() => tokenRef.current);
    setUnauthorizedHandler(() => setSession(null));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      isAuthenticated: session !== null,
      login,
      logout,
    }),
    [session, login, logout],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an <AuthProvider>");
  }
  return ctx;
}
