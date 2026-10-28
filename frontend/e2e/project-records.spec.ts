import { expect, test } from "@playwright/test";

test("records and reviews project evidence without changing existing navigation", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email address").fill(`project-record-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("Project-record-test-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.getByRole("link", { name: "Projects", exact: true }).click();
  await page.getByLabel("Project name", { exact: true }).fill("Recorded backend project");
  await page.getByLabel("Project goal").fill("Explain safe retries in interviews");
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByRole("heading", { name: "Recorded backend project" })).toBeVisible();
  await page.getByRole("button", { name: "Record a stage" }).click();
  await page.getByLabel("Stage title").fill("Protect duplicate writes");
  await page.getByLabel("Objective", { exact: true }).fill("Make retry safe");
  await page.getByLabel("What changed").fill("Add database uniqueness");
  await page.getByLabel("Source label").fill("docs/stage.md");
  await page.getByLabel("Source excerpt").fill("Database uniqueness makes retry safe.");
  await page.getByLabel("Exact quote").fill("uniqueness makes retry safe");
  await page.getByRole("button", { name: "Save record draft" }).click();
  await expect(page.getByRole("heading", { name: "Protect duplicate writes" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirm record" })).toBeDisabled();
  await page.getByLabel("Your actual contribution").fill("I designed and tested the unique constraint.");
  await page.getByRole("button", { name: "Confirm record" }).click();
  await expect(page.getByText("confirmed · v2")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Recorded backend project", exact: true }).click();
  await page.getByLabel("Record status").selectOption("confirmed");
  await page.getByLabel("Search records").fill("uniqueness");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Protect duplicate writes" })).toBeVisible();
  await page.getByText("Record details and sources").click();
  await expect(page.locator("blockquote")).toHaveText("uniqueness makes retry safe");
  await page.getByRole("button", { name: "Withdraw record" }).click();
  await expect(page.getByText("No records in this view.")).toBeVisible();
  await page.getByLabel("Record status").selectOption("withdrawn");
  await expect(page.getByText(/Withdrawn: keep for history/)).toBeVisible();
  for (const name of ["Experiences", "Jobs", "Action Items", "Dashboard"]) {
    await expect(page.getByRole("link", { name, exact: true })).toBeVisible();
  }
});
