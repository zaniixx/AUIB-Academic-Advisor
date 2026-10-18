import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// The admin tests need the server's master token (ADVISOR_ADMIN_TOKEN): E2E_ADMIN_TOKEN=... npx playwright test.
// They leave the catalog as it was: uploads are previewed (dry runs), the program is only
// checked, and the backup that is restored is the one made a moment before. The audit log
// gains the backup and restore entries.
const TOKEN = process.env.E2E_ADMIN_TOKEN;

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

test.skip(!TOKEN, "Set E2E_ADMIN_TOKEN to run the admin tests");

test("an admin previews uploads, checks a minor, and backs up and restores the data", async ({ page }, testInfo) => {
  // Once, on desktop: admins work there, and two copies of this test would back up and restore the
  // shared database at the same time, under the other tests.
  test.skip(testInfo.project.name !== "desktop", "admin work is done on desktop; one restore at a time");
  await page.goto("/admin");
  // The test student is not an admin (ADR 0009), so the page offers the master token.
  await expect(page.getByRole("heading", { name: "Admins only" })).toBeVisible();
  await page.getByLabel("Master token").fill(TOKEN!);
  await page.getByRole("button", { name: "Use the master token" }).click();
  await expect(page.getByRole("heading", { name: "Course data" })).toBeVisible();
  await expectAccessible(page);

  // People: the master token adds an advisor, then removes them again.
  const advisor = `e2e.advisor.${testInfo.project.name}@auib.edu.iq`;
  await page.getByRole("tab", { name: "People" }).click();
  await page.getByLabel("AUIB email address").fill(advisor);
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByRole("list", { name: "Admins and advisors" }).getByText(advisor)).toBeVisible();
  await expectAccessible(page);
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: `Remove ${advisor} (Advisor)` }).click();
  await expect(page.getByText(advisor)).toHaveCount(0);

  // Courses: edit dialog, then a bulk upload preview that saves nothing.
  await page.getByRole("tab", { name: "Courses" }).click();
  await page.getByPlaceholder("Course code or title").fill("CSC 231");
  await page.getByRole("button", { name: "Edit CSC 231" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Edit CSC 231" })).toBeVisible();
  await expect(dialog.getByLabel("Title")).toHaveValue(/Data Structure/);
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Close" }).first().click();
  await page.getByRole("button", { name: "Upload many courses" }).click();
  await page.getByLabel("Paste from a spreadsheet, or type CSV").fill("code\ttitle\tunits\nCSC 231\t\t4\nNOPE\tBad\t3");
  await page.getByRole("button", { name: "Check", exact: true }).click();
  await expect(page.getByText("Fix the rows marked Problem, then check again")).toBeVisible();
  await expect(page.getByRole("cell", { name: "credits: 3 → 4" })).toBeVisible();
  await expectAccessible(page);

  // Majors and minors: a minor drafted by hand is checked, not saved.
  await page.getByRole("tab", { name: "Majors and minors" }).click();
  await expect(page.getByText("Computer Science", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "New minor" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Preview Minor");
  await page.getByLabel("Courses (separate with commas)").fill("CSC 231, ZZZ 999");
  await page.getByRole("button", { name: "Check", exact: true }).click();
  await expect(page.getByText(/problem\(s\) to fix before saving/)).toBeVisible();
  await expect(page.getByText(/ZZZ 999/).last()).toBeVisible();
  await expectAccessible(page);
  await page.getByRole("button", { name: "Back to the list" }).click();

  // Term schedules: a preview lists skipped rows and saves nothing.
  await page.getByRole("tab", { name: "Term schedules" }).click();
  await page.getByRole("button", { name: "Upload a term's schedule" }).click();
  await page.getByLabel("Paste from a spreadsheet, or type CSV").fill("code,section,days,time\nCSC 231,01,MW,9:00-10:15\nXYZ 999,01,TR,11:00");
  await page.getByRole("button", { name: "Check", exact: true }).click();
  await expect(page.getByText("Preview: nothing is saved yet")).toBeVisible();
  await expect(page.getByRole("cell", { name: /Not in the course catalog/ })).toBeVisible();
  await expectAccessible(page);

  // Backup and restore: a random key and the encrypted file, then the same file restored. The data is
  // restored to what it already was, and the data from before the restore downloads as an undo file.
  await page.getByRole("tab", { name: "Backup and restore" }).click();
  await page.getByRole("button", { name: "Create a random key" }).click();
  await expect(page.getByText("Save this key now")).toBeVisible();
  const key = (await page.getByText(/^[A-Za-z0-9_-]{43}$/).textContent())!;
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download backup" }).click();
  const backup = await download;
  expect(backup.suggestedFilename()).toMatch(/^auib-advisor-backup-\d{8}-\d{4}\.aab$/);
  await expectAccessible(page);

  await page.getByLabel("Backup file (.aab)").setInputFiles(await backup.path());
  await page.getByLabel("Its passphrase or key").fill("not the key");
  await page.getByRole("button", { name: "Check the file" }).click();
  await expect(page.getByText(/Wrong passphrase/)).toBeVisible();
  await page.getByLabel("Its passphrase or key").fill(key);
  await page.getByRole("button", { name: "Check the file" }).click();
  await expect(page.getByText(/^Backup made on/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Restore this backup" })).toBeDisabled();
  await expectAccessible(page);
  await page.getByLabel("Type RESTORE to confirm").fill("restore");
  const undo = page.waitForEvent("download");
  await page.getByRole("button", { name: "Restore this backup" }).click();
  expect((await undo).suggestedFilename()).toMatch(/^auib-advisor-before-restore-\d{8}-\d{4}\.aab$/);
  await expect(page.getByText("Restored", { exact: true })).toBeVisible();
});
