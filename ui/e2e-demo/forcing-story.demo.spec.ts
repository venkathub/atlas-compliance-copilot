import { test, expect } from "@playwright/test";
import { installRoutes } from "../e2e/fixtures.ts";

/**
 * The 3-minute demo, automated (P6 Task 6 — the click-through in docs/DEMO.md).
 *
 * One pass that surfaces all four headline capabilities the demo must show:
 *   1. RBAC RAG      — Priya (compliance) gets a CITED, AI-generated answer;
 *   2. Agent + MCP   — the governed `open_draft_sar` action behind a human approval (HITL);
 *   3. Eval/trace    — the per-run execution trace, plus the Admin▸Evals gate snapshot;
 *   4. Cost          — the Admin▸Cost reduction panel.
 *
 * Deterministic: production `vite preview` build + pinned network mocks (fixtures.ts). The
 * Cost/Evals panels read the committed public snapshots (cost-summary.json / eval-summary.json),
 * so they render the REAL gate numbers without a live backend.
 */
test("3-min demo: RBAC RAG → agent MCP action → trace → cost → evals", async ({ page }) => {
  await installRoutes(page, "priya", { agent: true });

  // ── 0:00 Login as Priya (compliance) ──────────────────────────────────────
  await page.goto("/login");
  await page.getByRole("button", { name: /Priya/ }).click();
  await expect(page).toHaveURL(/\/chat/);

  // ── 0:20 RBAC RAG: governed-action question → cited, AI-generated answer ───
  await page.getByLabel("Investigate as governed action").check();
  await page
    .getByLabel("Ask a question")
    .fill("Any AML exceptions breaching the threshold for Northwind this quarter?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("AI-generated").first()).toBeVisible(); // EU AI Act transparency
  await expect(page.getByText(/1 breaches the \$10k threshold/)).toBeVisible(); // grounded + cited [1]

  // ── 0:50 Eval/TRACE view: the per-run execution trace (NIST AI RMF traceability) ──
  await page.getByRole("button", { name: /Execution trace/ }).click();
  await expect(page.getByTestId("trace-steps")).toBeVisible();
  await expect(page.getByTestId("trace-steps")).toContainText("retrieve");
  await expect(page.getByTestId("trace-steps")).toContainText("assess");

  // ── 1:10 Agent + MCP: the HITL approval card for the governed write ────────
  await expect(page.getByText(/Approval required/i)).toBeVisible();
  await expect(page.getByText(/requires human review/i)).toBeVisible();
  await expect(page.getByText("open_draft_sar")).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByTestId("draft-result")).toContainText("SAR-2026-000123");

  // ── 1:40 Admin ▸ Audit: the new SUCCESS row, chain verified ────────────────
  await page.getByRole("link", { name: "Admin" }).click();
  await expect(page).toHaveURL(/\/admin/);
  await page.getByRole("tab", { name: "Audit" }).click();
  await expect(page.getByText(/chain verified/i)).toBeVisible();
  const row = page.getByRole("row").filter({ hasText: "open_draft_sar" });
  await expect(row).toContainText("SUCCESS");
  await expect(row).toContainText("SAR-2026-000123");

  // ── 2:10 Admin ▸ Cost: the cost-reduction panel (the cost story) ───────────
  await page.getByRole("tab", { name: "Cost" }).click();
  await expect(page.getByText(/Cost reduction \(P3 cache \+ routing\)/)).toBeVisible();
  await expect(page.getByText("100%").first()).toBeVisible(); // costReductionPct (committed snapshot)
  await expect(page.getByText(/Live cost & latency \(Grafana\)/)).toBeVisible();

  // ── 2:40 Admin ▸ Evals: the gate snapshot (quality proof) ──────────────────
  await page.getByRole("tab", { name: "Evals" }).click();
  await expect(page.getByText(/RAG gate \(RAGAS \+ adversarial\)/)).toBeVisible();
  await expect(page.getByText(/Agent gate \(trajectory \+ safety\)/)).toBeVisible();
  await expect(page.getByText("Adversarial pass-rate")).toBeVisible();
  // Two PASS badges (RAG + agent gates) prove the committed quality gates are green.
  await expect(page.getByText("PASS", { exact: true })).toHaveCount(2);
});
