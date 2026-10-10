import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * Changing a plan: moving a course to another term (F6.1), comparing saved plans (F6.2), trying
 * another major or minor (F6.3), and courses that count toward more than one requirement (F1.7).
 */

const done = (term: string, grade: string, codes: string[]) =>
  codes.map((code) => ({ code, status: "completed", term, grade, units: 3 }));

// A second-year Computer Science student, saved the way the start wizard saves a guest's profile.
const PROFILE = {
  version: 1,
  programId: "casc-computer-science",
  minorId: null,
  attempts: [
    ...done("Fall 2025", "B", ["CSC 101", "MAT 111", "ENL 101", "UNI 101", "HIS 101"]),
    ...done("Spring 2026", "A-", ["CSC 140", "MAT 112", "ENL 201", "PSY 101", "BIO 101"]),
    ...["CSC 230", "CSC 132", "MAT 202", "ENL 210", "CHE 100"].map((code) => ({
      code,
      status: "in_progress",
      term: "Fall 2026",
      units: 3,
    })),
  ],
  preferences: {},
  updatedAt: "2026-10-08T10:00:00.000Z",
};

async function openPlan(page: Page, hash = "") {
  await page.goto("/");
  await page.evaluate((profile) => {
    localStorage.clear();
    localStorage.setItem("auib-advisor:profile", JSON.stringify(profile));
  }, PROFILE);
  await page.goto(`/plan${hash}`);
}

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.length} element(s)`)).toEqual([]);
}

async function shots(name: string, page: Page) {
  const { clientWidth, scrollWidth } = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(scrollWidth, `${name} scrolls sideways`).toBeLessThanOrEqual(clientWidth);
  await page.screenshot({ path: `e2e/.results/screens/${test.info().project.name}-${name}.png`, fullPage: true });
}

/** The suggested later terms, opened, and each term's card in order. */
async function laterTerms(page: Page): Promise<{ list: Locator; cards: Locator }> {
  await page.getByRole("button", { name: "Show the suggested terms" }).click();
  const list = page.getByRole("list", { name: "Suggested later terms" });
  return { list, cards: list.locator(":scope > li") };
}

const heading = (card: Locator) => card.getByRole("heading", { level: 3 }).textContent();

/** Picks up a course row by its title, as a mouse user would, and holds it over ``target``. */
async function dragOver(page: Page, row: Locator, target: Locator) {
  const from = (await row.locator("p span").first().boundingBox())!;
  const to = (await target.boundingBox())!;
  await page.mouse.move(from.x + 5, from.y + from.height / 2);
  await page.mouse.down();
  // The browser starts a drag only once the pointer has moved a little, so move in small steps.
  await page.mouse.move(from.x + 30, from.y + from.height / 2, { steps: 5 });
  // The middle of the term: its top can sit under the sticky tab bar.
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 10 });
}

/** Lets go of the dragged course over the term it was held over. */
async function drop(page: Page, target: Locator) {
  // The browser drops where the last drag-over happened, so move a little before letting go.
  const to = (await target.boundingBox())!;
  await page.mouse.move(to.x + to.width / 2 + 5, to.y + to.height / 2 + 5, { steps: 2 });
  await page.mouse.up();
}

test("a student moves a course from the move dialog (F6.1)", async ({ page }) => {
  await openPlan(page);
  const { list } = await laterTerms(page);
  const row = list.locator('li[draggable="true"]').filter({ hasNotText: /CSC 39[01]/ }).first();
  const code = (await row.getByRole("link").first().textContent())!;
  await row.getByRole("button", { name: `More about ${code}` }).click();
  await row.getByRole("button", { name: "Move to another term" }).click();

  const dialog = page.getByRole("dialog", { name: `Move ${code}` });
  await expect(dialog.getByRole("list", { name: "Terms" })).toBeVisible();
  // Every term says whether the course fits there and what that does to graduation.
  await expect(dialog.getByText(/^Graduation (stays|.*, \d+ terms? (later|earlier))/).first()).toBeVisible();
  await expectAccessible(page);
  await shots("10-move-dialog", page);

  const move = dialog.getByRole("button", { name: new RegExp(`^Move ${code} to `) }).first();
  const target = /to (.+)$/.exec((await move.getAttribute("aria-label"))!)![1];
  await move.click();
  await expect(dialog).toHaveCount(0);
  const card = page.locator("li", { has: page.getByRole("heading", { name: target, exact: true }) });
  await expect(card.getByRole("link", { name: code, exact: true })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: `Moved ${code} to ${target}.` })).toBeAttached();
});

test.describe("with a mouse", () => {
  // Tall enough for the term being dragged from and the one dropped on to be on screen together.
  test.use({ viewport: { width: 1440, height: 1600 } });

test("dragging a course shows which terms it fits and explains the ones it does not (F6.1)", async ({ page }) => {
  test.skip(test.info().project.name === "phone", "Dragging needs a mouse; phones use the move dialog");
  await openPlan(page);
  const { list, cards } = await laterTerms(page);
  await list.evaluate((element) => element.scrollIntoView({ block: "start" }));
  const count = await cards.count();
  const labels = await Promise.all([...Array(count).keys()].map((index) => heading(cards.nth(index))));

  // An internship runs in summer only, so a drop on a regular term is refused with the reason.
  const summer = cards.nth(labels.findIndex((label) => label?.startsWith("Summer")));
  const internship = summer.locator('li[draggable="true"]').filter({ hasText: /CSC 39[01]/ }).first();
  const internshipCode = (await internship.getByRole("link").first().textContent())!;
  const fall = cards.nth(labels.findIndex((label) => label?.startsWith("Fall")));
  await dragOver(page, internship, fall);
  await expect(fall.getByText(`${internshipCode} runs in Summer only, not in Fall.`)).toBeVisible();
  await drop(page, fall);
  const refused = page.getByRole("dialog", { name: `Move ${internshipCode}` });
  await expect(refused.getByText(new RegExp(`^${internshipCode} can't go in Fall`))).toBeVisible();
  await expectAccessible(page);
  await shots("11-drop-refused", page);
  await refused.getByRole("button", { name: "Close" }).click();

  // A course moved one term later, into the last term, fits: the term says so while it is dragged.
  const last = cards.nth(count - 1);
  const lastLabel = labels[count - 1]!;
  const before = cards.nth(labels.findLastIndex((label, index) => index < count - 1 && !label?.startsWith("Summer")));
  const course = before.locator('li[draggable="true"]').filter({ hasNotText: /CSC 39[01]/ }).first();
  const code = (await course.getByRole("link").first().textContent())!;
  await dragOver(page, course, last);
  await expect(last.getByText(/^Fits here\. Graduation/)).toBeVisible();
  await shots("12-dragging", page);
  await drop(page, last);
  const moved = page.locator("li", { has: page.getByRole("heading", { name: lastLabel, exact: true }) });
  await expect(moved.getByRole("link", { name: code, exact: true })).toBeVisible();
  await expect(moved.locator("li", { hasText: code }).getByText("Kept here")).toBeVisible();
});
});

test("a student compares saved plans and another major (F6.2, F6.3, F1.7)", async ({ page }) => {
  await openPlan(page, "#compare");
  await expect(page.getByRole("heading", { name: "Compare plans" })).toBeVisible();
  await expect(page.getByText(/^No saved plans yet\./)).toBeVisible();
  await page.getByLabel("Name for this plan").fill("Computer Science as is");
  await page.getByRole("button", { name: "Save this plan" }).click();
  const table = page.getByRole("table", { name: "Your current plan and your saved plans, side by side" });
  await expect(table.getByRole("columnheader", { name: /^Computer Science as is/ })).toBeVisible();
  await expect(table.getByText("Same finish")).toBeVisible();

  // F6.3: the same major with a minor; the result can be saved to compare.
  await page.getByLabel("Minor", { exact: true }).selectOption({ label: "Psychology" });
  await expect(page.getByText(/^You would (still )?graduate in/)).toBeVisible();
  await expect(page.getByText(/None of your credits would be lost\./)).toBeVisible();
  await page.getByRole("button", { name: "Save as a plan to compare" }).click();
  await expect(table.getByRole("columnheader", { name: /^Computer Science \+ Psychology/ })).toBeVisible();

  // Another major: computer science courses stop counting, and the table says which.
  await page.getByLabel("Major", { exact: true }).selectOption({ label: "Psychology" });
  const transfer = page.getByRole("table", { name: "Where each of your courses counts now and after the change" });
  await expect(transfer.getByRole("row", { name: /CSC 230/ })).toContainText("Does not count");
  await expect(transfer.getByRole("row", { name: /ENL 101/ })).toContainText("Communication skills");
  await expect(page.getByRole("button", { name: "Switch my plan to Psychology" })).toBeVisible();
  await expectAccessible(page);
  await shots("13-compare", page);

  // A saved plan becomes the student's plan.
  page.once("dialog", (confirm) => confirm.accept());
  await table.getByRole("button", { name: "Use this plan" }).last().click();
  await expect(page.getByText("Computer Science · Minor in Psychology")).toBeVisible();

  // F1.7: PSY 101 counts toward the major and the minor; the requirements say so.
  await page.getByRole("tab", { name: "Requirements" }).click();
  await expect(page.getByText("PSY 101 also counts toward Psychology minor: PSY 101 first.")).toBeAttached();
  await page.getByRole("tab", { name: "Plan", exact: true }).click();
  await page.getByRole("button", { name: "Show the suggested terms" }).click();
  await expect(page.getByText("Counts twice").first()).toBeVisible();

  // "Clear my data" removes the saved plans too.
  page.once("dialog", (confirm) => confirm.accept());
  await page.getByRole("button", { name: "Clear my data" }).click();
  await expect(page).toHaveURL(/\/$/);
  expect(await page.evaluate(() => localStorage.getItem("auib-advisor:scenarios"))).toBeNull();
});
