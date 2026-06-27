import { test, expect } from "@playwright/test";
import { installRoutes } from "./fixtures.ts";

/**
 * Negative-access UX (§4.4): a sub-compliance identity (analyst-bob) gets NO Admin tab
 * (the clearance gate surfaced) and an answer with no restricted content — the P1 RBAC
 * guarantee made visible. (The backend re-enforces RBAC regardless; this asserts the UX.)
 */
test("analyst: no Admin tab, no restricted content", async ({ page }) => {
  await installRoutes(page, "analyst-bob", {
    queryAnswer: "No exceptions are visible at your clearance level.",
  });

  await page.goto("/login");
  await page.getByRole("button", { name: /Bob/ }).click();
  await expect(page).toHaveURL(/\/chat/);

  // The Admin tab is NOT rendered for sub-compliance clearance.
  await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);

  // Asking the forcing question returns a clearance-filtered answer (no restricted data).
  await page.getByLabel("Ask a question").fill("Show me the AML exceptions and SAR drafts.");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/no exceptions are visible at your clearance level/i)).toBeVisible();
  await expect(page.getByText(/SAR-2026/)).toHaveCount(0);

  // Directly navigating to /admin is bounced away (route guard). A fresh load drops the
  // in-memory session (D-P5-6), so this lands on /login — never the admin area.
  await page.goto("/admin");
  await expect(page).not.toHaveURL(/\/admin/);
  await expect(page.getByText("Admin (read-only)")).toHaveCount(0);
});
