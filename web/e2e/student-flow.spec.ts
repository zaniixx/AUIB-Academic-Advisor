import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// A synthetic Course History paste in the SIS layout: menus, one cell per line, a
// duplicated status, and one in-progress row with no status that the student must fix.
const PASTE = [
  "Student Center",
  "Academic Record",
  "Course History",
  "Course",
  "Description",
  "Term",
  "Grade",
  "Units",
  "Status",
  ...["CSC 101", "Introduction to Computer Science", "2025/2026 Fall", "A", "3.00", "Taken", "Taken"],
  ...["MAT 111", "Calculus and Analytic Geometry I", "2025/2026 Fall", "B+", "3.00", "Taken"],
  ...["ENL 101", "Expository Writing", "2025/2026 Fall", "A-", "3.00", "Taken"],
  ...["UNI 101", "First-Year University Experience", "2025/2026 Fall", "A", "3.00", "Taken"],
  ...["CSC 140", "Introduction to C Programming", "2025/2026 Spring", "B", "3.00", "Taken"],
  ...["MAT 112", "Calculus II", "2025/2026 Spring", "B-", "3.00", "Taken"],
  ...["CSC 230", "Object-Oriented Computing", "2026/2027 Fall", "3.00", "In Progress"],
  ...["CSC 132", "Digital Logic", "2026/2027 Fall", "3.00"],
  "Return to Top",
].join("\n");

// Every step is checked for sideways scrolling (the 380px-phone requirement) and saved as a screenshot.
async function shots(name: string, page: Page) {
  const { clientWidth, scrollWidth } = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(scrollWidth, `${name} scrolls sideways`).toBeLessThanOrEqual(clientWidth);
  await page.screenshot({ path: `e2e/.results/screens/${test.info().project.name}-${name}.png`, fullPage: true });
}

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.length} element(s)`)).toEqual([]);
}

test("a guest pastes their history and gets a plan", async ({ page }) => {
  await page.goto("/");
  await expectAccessible(page);
  await page.getByRole("link", { name: "Start planning" }).first().click();

  await expect(page.getByLabel("Your major")).toHaveValue("casc-computer-science");
  await shots("1-program", page);
  await page.getByRole("button", { name: "Next", exact: true }).click();

  await page.getByLabel("Pasted Course History").fill(PASTE);
  await shots("2-history", page);
  await page.getByRole("button", { name: "Read my courses" }).click();

  await expect(page.getByText("8 course attempts found")).toBeVisible();
  await expect(page.getByText("Choose a status for 1 course")).toBeVisible();
  await page.getByLabel("Status of CSC 132").selectOption("in_progress");
  await expectAccessible(page);
  await shots("3-review", page);
  await page.getByRole("button", { name: "Next", exact: true }).click();

  await page.getByText("AI and machine learning").click();
  await page.getByText("Data scientist").click();
  await shots("4-goals", page);
  await page.getByRole("button", { name: "See my plan" }).click();

  await expect(page).toHaveURL(/\/plan$/);
  await expect(page.getByText("Expected graduation", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Term by term" })).toBeVisible();
  await expect(page.getByText("This term")).toBeVisible();
  await expectAccessible(page);
  await shots("5-plan", page);

  // GPA card: CGPA, then last term, then the retake that helps most.
  const gpa = page.getByRole("region", { name: "GPA" });
  await expect(gpa.getByText("3.45", { exact: true })).toBeVisible(); // (4+3.3+3.7+4+3+2.7)/6
  await expect(gpa.getByText("Last term GPA")).toBeVisible();
  await expect(gpa.getByText("2.85 Spring 2026")).toBeVisible(); // B and B- in Spring 2026
  await expect(gpa.getByText("MAT 112", { exact: true })).toBeVisible();

  // The degree map: selecting a course explains what it needs and opens.
  await expect(page.getByRole("heading", { name: "Degree map" })).toBeVisible();
  await page.getByRole("button", { name: /^CSC 231 Data Structure, Planned/ }).click();
  await expect(page.getByText(/^Needs first: .*CSC 230/)).toBeVisible();
  await shots("5b-map", page);

  // Internships run in summer only.
  const summer = page.locator("li", { has: page.getByRole("heading", { name: /^Summer \d{4}$/ }) }).first();
  await expect(summer).toContainText("CSC 390");

  // "Replace with" swaps an elective for another course that fits the same term.
  const replace = page.getByLabel(/^Replace with/).first();
  const choice = await replace.locator("option").nth(1).getAttribute("value");
  expect(choice).toBeTruthy();
  await replace.selectOption(choice!);
  await expect(
    page.locator("li").filter({ hasText: choice! }).filter({ hasText: "Kept here" }).first(),
  ).toBeVisible();
  await shots("5c-replaced", page);

  await page.getByRole("button", { name: "What if I delay it?" }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Graduation", { exact: true })).toBeVisible();
  await shots("6-what-if", page);
  await dialog.getByRole("button", { name: "Close" }).last().click();

  // The document for the advisor: the next term in detail, every term at a glance, and the notice
  // that approval is not a promise of courses. Printing leaves out the site's header and the buttons.
  await page.getByRole("link", { name: "Print for my advisor" }).click();
  await expect(page).toHaveURL(/\/plan\/print$/);
  await expect(page.getByRole("heading", { name: "Course plan for advising" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^1\. (Spring|Summer|Fall) \d{4}: planned courses$/ })).toBeVisible();
  await expect(page.getByRole("note")).toContainText(
    "Even if an advisor reviews, approves or signs this plan, that is not a promise that these classes will be scheduled in upcoming terms.",
  );
  await expect(page.getByLabel("Paper size")).toHaveValue("a4");
  // An open choice prints as a blank line to write the chosen course on.
  await expect(page.getByText(/^Open choice for .*: write in the course$/).first()).toBeAttached();
  // Every term at a glance is left out until the student adds it.
  await expect(page.getByRole("heading", { name: /Every term at a glance/ })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "2. Advisor review" })).toBeVisible();
  await expectAccessible(page);
  await shots("8-advisor-document", page);
  const overview = page.getByRole("button", { name: "Include every term at a glance" });
  await expect(overview).toHaveAttribute("aria-pressed", "false");
  await overview.click();
  await expect(overview).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("region", { name: "Courses by term" })).toContainText("CSC 390");
  await expect(page.getByRole("heading", { name: "3. Advisor review" })).toBeVisible();
  await expectAccessible(page);
  await shots("8b-advisor-document-all-terms", page);
  await page.emulateMedia({ media: "print" });
  await expect(page.getByRole("button", { name: "Print or save as PDF" })).toBeHidden();
  await expect(page.getByRole("navigation", { name: "Main" })).toBeHidden();
  await expect(page.getByRole("heading", { name: "2. Every term at a glance" })).toBeVisible();
  await page.emulateMedia({ media: "screen" });
  await page.getByRole("link", { name: "Back to my plan" }).click();
  await expect(page).toHaveURL(/\/plan$/);

  page.once("dialog", (confirm) => confirm.accept());
  await page.getByRole("button", { name: "Clear my data" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/plan");
  await expect(page.getByText("No plan yet")).toBeVisible();
});

test("a new student adds a minor and sees it in the plan and the advisor document", async ({ page }) => {
  await page.goto("/start");
  await page.getByLabel("Minor (optional)").selectOption({ label: "Psychology" });
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByRole("button", { name: "I'm a new student, skip" }).click();
  await page.getByRole("button", { name: "See my plan" }).click();

  await expect(page).toHaveURL(/\/plan$/);
  await expect(page.getByText("Computer Science · Minor in Psychology")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Minor in Psychology" })).toBeVisible();
  // PSY 101 opens the minor; the planner then picks five of the eight listed courses.
  await expect(page.locator("#plan").getByText("PSY 101", { exact: true })).toBeVisible();
  await expectAccessible(page);
  await shots("9-minor", page);

  await page.getByRole("link", { name: "Print for my advisor" }).click();
  await expect(page.getByText("Minor", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Include every term at a glance" }).click();
  await expect(page.getByRole("heading", { name: "Minor in Psychology once this plan is complete" })).toBeVisible();
  await expectAccessible(page);
});

test("course pages show rules beside their SIS source", async ({ page }) => {
  await page.goto("/courses");
  await page.getByLabel("Search by code or title").fill("data structure");
  await page.getByRole("link", { name: /CSC 231/ }).click();
  await expect(page.getByRole("heading", { name: /CSC 231/ })).toBeVisible();
  await expect(page.getByText("CSC 230 and MAT 111", { exact: true })).toBeVisible();
  await expect(page.getByText(/From the SIS description/)).toBeVisible();
  await expectAccessible(page);
  await shots("7-course", page);
});

test("the privacy page explains storage and offers clearing", async ({ page }) => {
  await page.goto("/privacy");
  await expect(page.getByRole("button", { name: "Clear my data from this browser" })).toBeVisible();
  await expectAccessible(page);
});
