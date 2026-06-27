import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the DEMO walkthrough suite (P6 Task 6).
 *
 * Separate from the acceptance gate (`playwright.config.ts`, testDir ./e2e) so the demo
 * click-through can evolve without touching the CI gate. Same deterministic setup: runs against
 * the production `vite preview` build with pinned network mocks (no live model). This is the
 * automated form of docs/DEMO.md — the exact <3-minute path, asserted end to end.
 *
 *   cd ui && npm run e2e:demo
 */
export default defineConfig({
  testDir: "./e2e-demo",
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
