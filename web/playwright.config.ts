import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against a running stack (for example `docker compose up`, or the
 * API plus `npm run dev`). Point them elsewhere with E2E_BASE_URL.
 */
export default defineConfig({
  testDir: "./e2e",
  // Signs a test student in first (F9.1); see e2e/global-setup.ts.
  globalSetup: "./e2e/global-setup.ts",
  outputDir: "./e2e/.results",
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never", outputFolder: "e2e/.report" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    storageState: "e2e/.auth/student.json",
    trace: "retain-on-failure",
    // Animations are switched off (as for a student who asks for less motion), so accessibility
    // checks and screenshots never catch an element halfway through fading in.
    contextOptions: { reducedMotion: "reduce" },
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    // The requirements ask for every screen to work on a 380px-wide phone.
    { name: "phone", use: { ...devices["Pixel 7"], viewport: { width: 380, height: 800 } } },
  ],
});
