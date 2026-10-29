// Captures UI preview screenshots from a running frontend with synthetic data.
// Usage: node scripts/capture-preview.mjs <baseUrl> <outDir> <email> <password>
import { mkdirSync } from "node:fs";
import path from "node:path";

import { chromium } from "@playwright/test";

const [baseUrl = "http://127.0.0.1:3000", outDir = "preview", email, password] = process.argv.slice(2);
if (!email || !password) throw new Error("email and password are required");
mkdirSync(outDir, { recursive: true });

const viewports = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 400, height: 860 },
];

const browser = await chromium.launch({ channel: process.env.PREVIEW_BROWSER_CHANNEL || undefined });
for (const viewport of viewports) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 2 });
  const page = await context.newPage();
  // Grow the viewport to the document height instead of fullPage stitching, so sticky elements render in place.
  const shot = async (name, fullPage = true) => {
    if (fullPage) {
      const height = await page.evaluate(() => document.documentElement.scrollHeight);
      await page.setViewportSize({ width: viewport.width, height: Math.max(viewport.height, height) });
    }
    await page.screenshot({ path: path.join(outDir, `${viewport.name}-${name}.png`) });
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
  };

  await page.goto(`${baseUrl}/login`);
  await page.waitForLoadState("networkidle");
  await shot("login", false);

  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
  await page.getByText("Application pipeline").waitFor();
  await page.getByRole("region", { name: "Recently updated" }).getByRole("link").first().waitFor();
  await page.waitForTimeout(300);
  await shot("dashboard");

  await page.goto(`${baseUrl}/jobs`);
  await page.getByRole("region", { name: "Applied jobs" }).waitFor();
  await page.getByRole("link", { name: /Backend Engineer Intern/ }).first().waitFor();
  await shot("jobs");

  await page.getByRole("link", { name: /Backend Engineer Intern/ }).first().click();
  await page.waitForURL("**/jobs/*");
  const parse = page.getByRole("button", { name: "Parse description" });
  const parsed = page.getByText("Must Have").first();
  await Promise.race([parse.waitFor(), parsed.waitFor()]);
  if (await parse.isVisible()) {
    await parse.click();
    await page.getByText("Must Have").first().waitFor({ timeout: 60_000 });
    await page.getByRole("button", { name: "Analyze evidence" }).click();
    await Promise.race([page.getByText("Supported").first().waitFor({ timeout: 90_000 }), page.getByText("Too many requests").first().waitFor({ timeout: 90_000 })]);
  }
  await page.waitForTimeout(500);
  await shot("job-detail");

  for (const route of ["experiences", "projects", "action-items"]) {
    await page.goto(`${baseUrl}/${route}`);
    await page.waitForLoadState("networkidle");
    if (route === "projects") {
      await page.getByText("Record details and sources").first().click();
    }
    await shot(route);
  }
  await context.close();
}
await browser.close();
console.log(`saved screenshots to ${outDir}`);
