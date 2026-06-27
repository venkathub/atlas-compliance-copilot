import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E config (P5 Task 9 — the headline acceptance gate, G-P5-5).
 *
 * Runs against the PRODUCTION build served by `vite preview` (CSP-clean, prod-shaped).
 * Backend responses are PINNED via per-test network mocking (page.route/route.fulfill)
 * for determinism — no live-model variance in the gate (the live GPU variant is on-demand).
 * `reducedMotion: reduce` makes the client-side progressive reveal instant, so the cited
 * answer is asserted deterministically.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["html", { open: "never" }], ["list"]] : "list",
  use: {
    baseURL: "http://localhost:4173",
    reducedMotion: "reduce",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run preview -- --port 4173 --strictPort",
    url: "http://localhost:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
