import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { installRoutes, AGENT_AWAITING } from "./fixtures.ts";

/**
 * LLM05 live render-boundary check (§4.2, hard gate) + axe-core a11y smoke (G-P5-5).
 */

test("LLM05: an XSS-laden answer/citation renders inert in the browser", async ({ page }) => {
  // A run whose answer + citation carry XSS payloads.
  const xssRun = {
    ...AGENT_AWAITING,
    answer: 'Result <script>window.__xss=1</script> <img src=x onerror="window.__xss=1"> [1].',
    citations: [
      {
        n: 1,
        documentId: "uuid-1",
        clearance: "compliance",
        snippet: "<script>window.__xss=1</script><img src=x onerror=window.__xss=1>",
      },
    ],
  };
  await page.route("**/v1/auth/token", (r) =>
    r.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        token: "jwt-priya",
        tokenType: "Bearer",
        expiresIn: 3600,
        subject: "priya",
        clearance: "compliance",
      }),
    }),
  );
  await page.route("**/v1/agent/runs", (r) =>
    r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(xssRun) }),
  );

  // Fail loudly if any injected script triggers a dialog or a console error.
  let dialogFired = false;
  page.on("dialog", async (d) => {
    dialogFired = true;
    await d.dismiss();
  });
  const consoleErrors: string[] = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));

  await page.goto("/login");
  await page.getByRole("button", { name: /Priya/ }).click();
  await page.getByLabel("Investigate as governed action").check();
  await page.getByLabel("Ask a question").fill("show exceptions");
  await page.getByRole("button", { name: "Send" }).click();

  // Open the citation popover too (renders the malicious snippet).
  await expect(page.getByText(/Approval required/i)).toBeVisible();
  await page.getByRole("button", { name: "[1]" }).click();

  // The injected script never executed; no <script> element survived sanitization.
  expect(
    await page.evaluate(() => (window as unknown as { __xss?: number }).__xss),
  ).toBeUndefined();
  expect(dialogFired).toBe(false);
  expect(await page.locator("script:has-text('__xss')").count()).toBe(0);
  expect(consoleErrors.join("\n")).not.toMatch(/__xss/);
});

test("a11y: chat page has no critical/serious violations", async ({ page }) => {
  await installRoutes(page, "priya", { agent: true });
  await page.goto("/login");
  await page.getByRole("button", { name: /Priya/ }).click();
  await expect(page).toHaveURL(/\/chat/);

  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious",
  );
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
});

test("a11y: admin page has no critical/serious violations", async ({ page }) => {
  await installRoutes(page, "priya", { agent: true });
  await page.goto("/login");
  await page.getByRole("button", { name: /Priya/ }).click();
  await page.getByRole("link", { name: "Admin" }).click();
  await expect(page).toHaveURL(/\/admin/);

  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious",
  );
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
});
