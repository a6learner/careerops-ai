import { expect, test } from "@playwright/test";

const demoPacing = process.env.CAREEROPS_E2E_DEMO_PACING === "1";
const pauseForNarration = async (milliseconds: number): Promise<void> => {
  if (demoPacing) {
    await new Promise((resolve) => setTimeout(resolve, milliseconds));
  }
};

test.setTimeout(demoPacing ? 360_000 : 120_000);

test("completes the fake-provider core loop through the same-origin frontend", async ({
  page,
  baseURL,
}) => {
  const browserOrigins = new Set<string>();
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.protocol === "http:" || url.protocol === "https:") {
      browserOrigins.add(url.origin);
    }
  });

  const runSuffix = Date.now();
  const email = `p110-${runSuffix}@example.com`;
  const experienceTitle = `Imported Backend Project ${runSuffix}`;
  const searchQuery = `Backend Engineer ${runSuffix}`;
  const jobTitle = `Junior ${searchQuery}`;

  await page.goto("/register");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill("P110-acceptance-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await pauseForNarration(20_000);

  await page.getByRole("link", { name: "Experiences" }).first().click();
  await page.getByLabel("Choose CV").setInputFiles({
    name: `careerops-${runSuffix}.md`,
    mimeType: "text/markdown",
    buffer: Buffer.from(
      `${experienceTitle}\nBuilt a reliable Python API with background workers, PostgreSQL, and evidence validation.`,
    ),
  });
  await expect(page.locator('input[name="title"]')).toHaveValue(experienceTitle, {
    timeout: 60_000,
  });
  await page.getByRole("button", { name: "Confirm as experience" }).click();
  await expect(page.getByRole("heading", { name: experienceTitle })).toBeVisible();
  await pauseForNarration(25_000);

  await page.getByRole("link", { name: "Jobs" }).first().click();
  await page.getByLabel("Keywords").fill(searchQuery);
  await page.getByLabel("Location").fill("Los Angeles");
  await page.getByLabel("Published within days").fill("14");
  await page.getByRole("button", { name: "Search jobs" }).click();
  await expect(page.getByRole("heading", { name: jobTitle })).toBeVisible({ timeout: 60_000 });
  const incompleteResultCard = page
    .getByText(/Observed .*Description required/)
    .first()
    .locator("..");
  await expect(incompleteResultCard).toBeVisible();
  await incompleteResultCard.getByRole("button", { name: "Review draft" }).click();
  await expect(page.getByRole("heading", { name: "Review job draft" })).toBeVisible();
  const confirmJob = page.getByRole("button", { name: "Confirm as job" });
  await expect(confirmJob).toBeDisabled();
  await page
    .getByRole("textbox", { name: "Job description" })
    .fill("Python experience is required. Kubernetes experience is required.");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(confirmJob).toBeEnabled();
  await confirmJob.click();
  await expect(page.getByRole("heading", { name: jobTitle })).toBeVisible();
  await pauseForNarration(25_000);

  await page.getByRole("button", { name: "Parse description" }).click();
  await expect(page.getByText("Python experience is required").last())
    .toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Kubernetes experience is required").last())
    .toBeVisible();
  await pauseForNarration(30_000);

  await page.getByRole("button", { name: "Analyze evidence" }).click();
  await expect(page.locator("blockquote").filter({ hasText: "Python" }))
    .toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/No validated positive evidence is available/)).toBeVisible();
  await pauseForNarration(40_000);
  await page.getByRole("button", { name: "Create action item" }).first().click();
  await expect(page.getByText("Action item created.")).toBeVisible();

  await page.getByLabel("Update status").selectOption("applied");
  await page.getByRole("button", { name: "Update" }).click();
  await page.reload();
  await expect(page.getByLabel("Update status")).toHaveValue("applied");
  await pauseForNarration(20_000);

  await page.getByRole("link", { name: "Action Items" }).first().click();
  const sourcedTask = page.locator('input[value^="Address gap:"]');
  await expect(sourcedTask).toBeVisible();
  await expect(page.getByText("From analysis gap")).toBeVisible();
  await page.getByLabel("Status").last().selectOption("done");
  await page.getByRole("button", { name: "Save" }).click();
  await page.reload();
  await expect(page.getByLabel("Status").last()).toHaveValue("done");
  await pauseForNarration(20_000);

  await page.getByRole("link", { name: "Dashboard" }).first().click();
  await expect(page.getByText("Applied", { exact: true }).locator("..").getByText("1"))
    .toBeVisible();
  await expect(
    page.getByText("Completed tasks").locator("xpath=../..").getByText("1", { exact: true }),
  ).toBeVisible();
  await pauseForNarration(20_000);

  expect(baseURL).toBeTruthy();
  expect([...browserOrigins]).toEqual([new URL(baseURL!).origin]);
});
