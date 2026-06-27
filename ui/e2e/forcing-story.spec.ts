import { test, expect } from "@playwright/test";
import { installRoutes } from "./fixtures.ts";

/**
 * The forcing story, full loop (the headline P5 acceptance gate, §4.4):
 * Priya logs in → asks the governed-action question → sees a cited answer → is shown the
 * proposed draft-SAR → APPROVES it (the HITL checkpoint) → sees the draftRef + trace →
 * Admin▸Audit shows the new SUCCESS row with chainVerified.
 */
test("Priya: login → cited answer → approve draft SAR → audit row", async ({ page }) => {
  await installRoutes(page, "priya", { agent: true });

  // 1. Login as Priya (compliance).
  await page.goto("/login");
  await page.getByRole("button", { name: /Priya/ }).click();

  // 2. Switch to governed-action mode (account/period prefilled) and ask.
  await expect(page).toHaveURL(/\/chat/);
  await page.getByLabel("Investigate as governed action").check();
  await page.getByLabel("Ask a question").fill("Any AML exceptions breaching the threshold?");
  await page.getByRole("button", { name: "Send" }).click();

  // 3. Cited, AI-generated answer + the HITL ApprovalCard with the proposed write.
  await expect(page.getByText("AI-generated").first()).toBeVisible();
  await expect(page.getByText(/1 breaches the \$10k threshold/)).toBeVisible();
  await expect(page.getByText(/Approval required/i)).toBeVisible();
  await expect(page.getByText(/requires human review/i)).toBeVisible();
  await expect(page.getByText("open_draft_sar")).toBeVisible();

  // 4. Approve → the governed write completes and the draft SAR ref is shown.
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByTestId("draft-result")).toContainText("SAR-2026-000123");

  // 5. Admin ▸ Audit shows the new SUCCESS row with a verified chain.
  await page.getByRole("link", { name: "Admin" }).click();
  await expect(page).toHaveURL(/\/admin/);
  await page.getByRole("tab", { name: "Audit" }).click();
  await expect(page.getByText(/chain verified/i)).toBeVisible();
  const row = page.getByRole("row").filter({ hasText: "open_draft_sar" });
  await expect(row).toContainText("SUCCESS");
  await expect(row).toContainText("SAR-2026-000123");
});
