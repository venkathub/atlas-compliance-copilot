import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./app/auth/AuthContext.tsx";
import { AppRoutes } from "./app/routes.tsx";

/**
 * Root application shell.
 *
 * AuthProvider holds the in-memory session and wires the apiClient seams
 * (Bearer attach + 401→login). The router exposes /login, /chat, and the
 * clearance-gated /admin. Chat/admin bodies are filled in later P5 tasks.
 */
export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
