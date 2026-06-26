/**
 * Root application shell — Task 0 skeleton (no app logic yet).
 *
 * Later P5 tasks layer in the router (/login, /chat, /admin), the in-memory auth
 * context (Task 1), the sanitized chat surface (Tasks 2–4), and the read-only admin
 * views (Task 6). For now this is a static placeholder that proves the toolchain
 * (Vite + React + TS + Tailwind) builds and renders.
 */
export function App() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center p-8">
      <div className="max-w-md text-center">
        <h1 className="text-2xl font-semibold">Atlas</h1>
        <p className="mt-2 text-slate-600">
          Enterprise AI operations copilot — UI skeleton (P5 Task 0).
        </p>
      </div>
    </main>
  );
}
