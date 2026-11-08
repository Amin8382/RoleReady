import { expect, test } from "@playwright/test";

const cv = "Synthetic candidate: built a Python pipeline with SQL validation and unit tests for a class project.";
const job = "This test role requires Python, SQL, data validation, model evaluation, and clear communication.";

test("upload, seven answers, resume, report, PDF and deletion", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Local workspace", { exact: true })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({ name: "synthetic-cv.txt", mimeType: "text/plain", buffer: Buffer.from(cv) });
  await expect(page.getByLabel("Your CV text")).toHaveValue(cv);
  await page.getByLabel("Job description", { exact: true }).fill(job);
  await expect(page.getByRole("button", { name: "Prepare my session" })).toBeEnabled();
  await page.screenshot({ path: "artifacts/workspace-desktop.png", fullPage: true });
  await page.getByRole("button", { name: "Prepare my session" }).click();
  await expect(page.getByRole("heading", { name: "Python evidence" })).toBeVisible();
  await page.getByRole("button", { name: "Enter the practice room" }).click();
  for (let i = 1; i <= 7; i++) {
    await page.getByLabel("Your answer", { exact: true }).fill(`For question ${i}, I would validate the approach with a separate test dataset.`);
    await page.getByRole("button", { name: "Get feedback", exact: true }).click();
    await expect(page.getByText("Synthetic test feedback: explain the validation approach in more detail.")).toBeVisible();
    if (i < 7) await page.getByRole("button", { name: "Next question" }).click();
  }
  await page.getByRole("button", { name: "Create cheat sheet" }).click();
  await expect(page.getByRole("heading", { name: "Your interview cheat sheet" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: /Data Scientist7\/7 answers/ }).first().click();
  await expect(page.getByRole("heading", { name: "Your interview cheat sheet" })).toBeVisible();
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PDF" }).click();
  expect((await downloaded).suggestedFilename()).toBe("RoleReady-cheat-sheet.pdf");
  await page.getByRole("button", { name: "Delete Data Scientist session", exact: true }).first().click();
  await page.getByRole("button", { name: "Delete session", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Your next role/ })).toBeVisible();
});

test("mobile layout and model failure keep the user's input", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByLabel("Your CV text").fill(cv);
  await page.getByLabel("Job description", { exact: true }).fill(job);
  await page.route("**/api/backend/v1/sessions", async route => {
    if (route.request().method() === "POST") await route.fulfill({ status: 503, json: { message: "Synthetic model outage. Please retry." } });
    else await route.continue();
  });
  await page.getByRole("button", { name: "Prepare my session" }).click();
  await expect(page.getByRole("alert")).toContainText("Synthetic model outage");
  await expect(page.getByLabel("Your CV text")).toHaveValue(cv);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "artifacts/workspace-mobile.png", fullPage: true });
});
