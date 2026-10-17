import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { SIGN_OUT_STATE } from "./global-setup";

// F9.1: course and program data are for AUIB students; the home and privacy pages stay open.

test.describe("before signing in", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("a visitor must sign in with an AUIB email to see courses and plans", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Start planning" }).first()).toBeVisible();

    for (const path of ["/plan", "/courses", "/start"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { name: "Sign in with your AUIB email" })).toBeVisible();
    }
    await expect(page.getByText(/CSC \d{3}/)).toHaveCount(0);

    const card = page.getByRole("region", { name: "Sign in with your AUIB email" });
    const email = card.getByLabel("AUIB email address");
    await email.fill("someone@gmail.com");
    await page.getByRole("button", { name: "Email me a code" }).click();
    await expect(card.getByRole("alert")).toHaveText("Use your AUIB email address (name@auib.edu.iq).");

    // A fresh address each run, so the one-code-a-minute limit never gets in the way of a retry.
    await email.fill(`e2e.${Date.now()}@auib.edu.iq`);
    await page.getByRole("button", { name: "Email me a code" }).click();
    await expect(page.getByText(/^We sent a 6-digit code to e2e\.\d+@auib\.edu\.iq/)).toBeVisible();
    await expect(page.getByRole("button", { name: /^Send a new code in \d+ s$/ })).toBeDisabled();

    await page.getByLabel("Code from the email").fill("000000");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(card.getByRole("alert")).toContainText("That code is not right");
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(results.violations.map((v) => `${v.id}: ${v.nodes.length} element(s)`)).toEqual([]);

    await page.goto("/privacy");
    await expect(page.getByRole("heading", { name: "Privacy and how this app works" })).toBeVisible();
  });
});

test.describe("signing out", () => {
  test.use({ storageState: SIGN_OUT_STATE });

  test("a student signs out and, on a shared computer, deletes their plan from the browser", async ({ page }, testInfo) => {
    // The session behind this test ends when it signs out, so it runs once (the menu is the same on phones).
    test.skip(testInfo.project.name !== "desktop", "one sign-out per session");
    await page.goto("/courses");
    await expect(page.getByRole("heading", { name: "Sign in with your AUIB email" })).toHaveCount(0);
    await page.evaluate(() => window.localStorage.setItem("auib-advisor:profile", "{}"));

    await page.getByRole("button", { name: /^Account: e2e@auib\.edu\.iq$/ }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByLabel(/Also delete my courses and plan from this browser/)).toBeChecked();
    await expect(dialog.getByLabel(/Sign out on all my devices and forget my email address/)).not.toBeChecked();
    await dialog.getByRole("button", { name: "Sign out" }).click();

    await expect(page.getByRole("heading", { name: "Sign in with your AUIB email" })).toBeVisible();
    expect(await page.evaluate(() => window.localStorage.getItem("auib-advisor:profile"))).toBeNull();
    await page.goto("/plan");
    await expect(page.getByRole("heading", { name: "Sign in with your AUIB email" })).toBeVisible();
  });
});
