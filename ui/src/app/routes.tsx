import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { LoginPage } from "./auth/LoginPage.tsx";
import { useAuth } from "./auth/AuthContext.tsx";
import { useClearance } from "./auth/useClearance.ts";
import { clearanceLabel } from "./auth/clearance.ts";
import { ChatPage } from "./chat/ChatPage.tsx";
import type { Clearance } from "../lib/types.ts";

/**
 * App routes — /login, /chat (authed), /admin (clearance-gated). The chat and admin
 * bodies are placeholders here; they are implemented in later P5 tasks (chat: 3–4,
 * admin: 6). The guards below are UX gating only — the backends re-enforce clearance.
 */

function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function RequireClearance({ min, children }: { min: Clearance; children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { hasAtLeast } = useClearance();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (!hasAtLeast(min)) {
    return <Navigate to="/chat" replace />;
  }
  return <>{children}</>;
}

function AppShell({ children }: { children: ReactNode }) {
  const { session, logout } = useAuth();
  const { hasAtLeast } = useClearance();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <span className="font-semibold">Atlas</span>
        <nav className="flex items-center gap-4 text-sm">
          <a href="/chat" className="hover:underline">
            Chat
          </a>
          {/* Admin tab renders only for compliance+ (UX gate; server re-enforces). */}
          {hasAtLeast("compliance") && (
            <a href="/admin" className="hover:underline">
              Admin
            </a>
          )}
          <span className="text-slate-500">
            {session?.subject} · {session ? clearanceLabel(session.clearance) : ""}
          </span>
          <button type="button" onClick={logout} className="text-slate-600 hover:underline">
            Log out
          </button>
        </nav>
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}

// Admin remains a placeholder until Task 6.
function AdminPlaceholder() {
  return <p className="text-slate-600">Admin (read-only) — implemented in P5 Task 6.</p>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/chat"
        element={
          <RequireAuth>
            <AppShell>
              <ChatPage />
            </AppShell>
          </RequireAuth>
        }
      />
      <Route
        path="/admin"
        element={
          <RequireClearance min="compliance">
            <AppShell>
              <AdminPlaceholder />
            </AppShell>
          </RequireClearance>
        }
      />
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}
