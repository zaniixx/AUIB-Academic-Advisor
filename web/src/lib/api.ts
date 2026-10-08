/**
 * Typed client for the AUIB Advisor API. Types come from the API's OpenAPI schema
 * (npm run gen:api), so a change on the server shows up here as a type error.
 * Requests go to the same origin under /api; nothing is sent anywhere else.
 */
import type { components } from "./api-types";

export type Schemas = components["schemas"];
export type MetaOut = Schemas["MetaOut"];
export type ProgramSummary = Schemas["ProgramSummaryOut"];
export type ProgramDetail = Schemas["ProgramDetailOut"];
export type Insights = Schemas["InsightsOut"];
export type CourseList = Schemas["CourseListOut"];
export type CourseDetail = Schemas["CourseOut"];
export type CourseRef = Schemas["CourseRef"];
export type HistoryParse = Schemas["HistoryParseOut"];
export type HistoryRow = Schemas["HistoryRowOut"];
export type StudentIn = Schemas["StudentIn"];
export type AttemptIn = Schemas["AttemptIn"];
export type PreferencesIn = Schemas["PreferencesIn"];
export type PlanOut = Schemas["PlanOut"];
export type MinorPlan = Schemas["MinorPlanOut"];
export type PlanItem = Schemas["PlanItemOut"];
export type PlannedTerm = Schemas["PlannedTermOut"];
export type GroupProgress = Schemas["GroupProgressOut"];
export type TermOut = Schemas["TermOut"];
export type WhatIfOut = Schemas["WhatIfOut"];
export type ChangeAction = Schemas["ChangeIn"]["action"];
export type Recommendations = Schemas["RecommendationsOut"];
export type AttemptStatus = Schemas["AttemptStatus"];
export type AdminRule = Schemas["AdminRuleOut"];
export type AdminRuleList = Schemas["AdminRuleListOut"];
export type RuleCheck = Schemas["RuleCheckOut"];
export type ImportRun = Schemas["ImportRunOut"];
export type AuditEntry = Schemas["AuditOut"];

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function describeError(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item: { loc?: unknown[]; msg?: string }) => {
        const where = (item.loc ?? []).filter((part) => part !== "body").join(" → ");
        return where ? `${where}: ${item.msg}` : item.msg;
      })
      .join("; ");
  }
  if (status === 429) return "Too many requests. Please wait a minute and try again.";
  return `The server answered ${status}. Please try again.`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection and try again.");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, describeError(response.status, body));
  return body as T;
}

const post = <T>(path: string, body: unknown, headers?: HeadersInit) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body), headers });

const bearer = (token: string): HeadersInit => ({ Authorization: `Bearer ${token}` });

export const api = {
  meta: () => request<MetaOut>("/api/v1/meta"),
  programs: (kind?: "major" | "minor") =>
    request<ProgramSummary[]>(`/api/v1/programs${kind ? `?kind=${kind}` : ""}`),
  program: (id: string) => request<ProgramDetail>(`/api/v1/programs/${encodeURIComponent(id)}`),
  insights: (id: string) => request<Insights>(`/api/v1/programs/${encodeURIComponent(id)}/insights`),
  courses: (q: string, offset = 0, limit = 25) =>
    request<CourseList>(
      `/api/v1/courses?${new URLSearchParams({ q, offset: String(offset), limit: String(limit) })}`,
    ),
  course: (code: string) => request<CourseDetail>(`/api/v1/courses/${encodeURIComponent(code)}`),
  parseHistory: (text: string) => post<HistoryParse>("/api/v1/history/parse", { text }),
  plan: (student: StudentIn) => post<PlanOut>("/api/v1/planner/plan", student),
  whatIf: (student: StudentIn, code: string, action: ChangeAction) =>
    post<WhatIfOut>("/api/v1/planner/what-if", { ...student, change: { code, action } }),
  recommendations: (student: StudentIn) => post<Recommendations>("/api/v1/planner/recommendations", student),
  admin: {
    rules: (token: string, show: string, q: string, offset = 0) =>
      request<AdminRuleList>(
        `/api/v1/admin/rules?${new URLSearchParams({ show, q, offset: String(offset), limit: "25" })}`,
        { headers: bearer(token) },
      ),
    check: (token: string, rule: string) => post<RuleCheck>("/api/v1/admin/rules/check", { rule }, bearer(token)),
    correct: (token: string, id: number, rule: string, note: string | null) =>
      request<AdminRule>(`/api/v1/admin/rules/${id}`, {
        method: "PUT",
        body: JSON.stringify({ rule, note }),
        headers: bearer(token),
      }),
    approve: (token: string, id: number) =>
      request<AdminRule>(`/api/v1/admin/rules/${id}/approve`, { method: "POST", headers: bearer(token) }),
    revert: (token: string, id: number) =>
      request<AdminRule>(`/api/v1/admin/rules/${id}/override`, { method: "DELETE", headers: bearer(token) }),
    imports: (token: string) => request<ImportRun[]>("/api/v1/admin/imports", { headers: bearer(token) }),
    audit: (token: string) => request<AuditEntry[]>("/api/v1/admin/audit", { headers: bearer(token) }),
  },
};
