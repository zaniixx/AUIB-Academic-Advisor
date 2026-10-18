import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { FullConfig } from "@playwright/test";

/**
 * F9.1: course and program data need a signed-in AUIB student, and a test cannot read the emailed
 * code. So each run starts sessions with the API's `issue-session` command and hands the browsers
 * their cookie. CI passes tokens it issued inside the stack (E2E_SESSION_TOKEN, E2E_SIGN_OUT_TOKEN);
 * a local run calls the command with the API's own Python.
 */
export const STUDENT_STATE = "e2e/.auth/student.json";
export const SIGN_OUT_STATE = "e2e/.auth/sign-out.json";
export const E2E_EMAIL = "e2e@auib.edu.iq";
/** Why a test that plans is skipped on a server without course data, as on GitHub's CI (ADR 0008). */
export const NEEDS_COURSE_DATA = "needs the course data, which this server does not have (CI on GitHub runs without it)";

function issueLocally(): string {
  const api = path.resolve(process.cwd(), "..", "api");
  const python = [path.join(api, ".venv", "Scripts", "python.exe"), path.join(api, ".venv", "bin", "python")].find(
    existsSync,
  );
  if (!python) throw new Error("Set E2E_SESSION_TOKEN, or create the API's virtual environment (api/.venv)");
  return execFileSync(python, ["-m", "app.cli", "issue-session", E2E_EMAIL], { cwd: api, encoding: "utf-8" }).trim();
}

function writeState(file: string, baseURL: string, token: string) {
  const { hostname } = new URL(baseURL);
  mkdirSync(path.dirname(file), { recursive: true });
  const cookie = { name: "advisor_session", value: token, domain: hostname, path: "/api", expires: -1 };
  writeFileSync(
    file,
    JSON.stringify({ cookies: [{ ...cookie, httpOnly: true, secure: false, sameSite: "Lax" }], origins: [] }),
  );
}

async function serverHasCourseData(baseURL: string): Promise<boolean> {
  try {
    const ready = (await (await fetch(new URL("/api/ready", baseURL))).json()) as { programs?: number };
    return (ready.programs ?? 0) > 0;
  } catch {
    return true; // an unreachable server is reported by the tests themselves
  }
}

export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL ?? "http://localhost:3000";
  writeState(STUDENT_STATE, baseURL, process.env.E2E_SESSION_TOKEN || issueLocally());
  writeState(SIGN_OUT_STATE, baseURL, process.env.E2E_SIGN_OUT_TOKEN || issueLocally());
  // Read by the tests that plan (test.skip): the workers inherit this environment.
  process.env.E2E_COURSE_DATA = (await serverHasCourseData(baseURL)) ? "1" : "";
}
