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
export type TermChoice = Schemas["TermChoiceOut"];
export type Building = Schemas["BuildingOut"];
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
export type AdminCourseSummary = Schemas["AdminCourseSummaryOut"];
export type AdminCourseList = Schemas["AdminCourseListOut"];
export type AdminCourse = Schemas["AdminCourseOut"];
export type CourseFields = Schemas["CourseFieldsIn"];
export type CourseCreate = Schemas["CourseCreateIn"];
export type TableUpload = Schemas["TableIn"];
export type UploadRow = Schemas["RowOut"];
export type CourseBulk = Schemas["CourseBulkOut"];
export type AdminProgramSummary = Schemas["AdminProgramSummaryOut"];
export type AdminProgram = Schemas["AdminProgramOut"];
export type GroupDraftOut = Schemas["GroupDraftOut"];
export type ProgramDraft = Schemas["ProgramDraftIn"];
export type GroupDraft = Schemas["GroupDraftIn"];
export type Finding = Schemas["FindingOut"];
export type ProgramCheck = Schemas["ProgramCheckOut"];
export type ProgramSave = Schemas["ProgramSaveOut"];
export type ScheduleSummary = Schemas["ScheduleSummaryOut"];
export type Schedule = Schemas["ScheduleOut"];
export type ScheduleUpload = Schemas["ScheduleUploadOut"];
export type TermOfferings = Schemas["TermOfferingsOut"];
export type BackupCheck = Schemas["BackupCheckOut"];
export type ProgramVersion = Schemas["ProgramVersionOut"];
export type GpaPlan = Schemas["GpaPlanOut"];
export type ExpectedGrade = Schemas["ExpectedGradeIn"];
export type RestoreResult = Schemas["RestoreOut"];

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

const put = <T>(path: string, body: unknown, headers?: HeadersInit) =>
  request<T>(path, { method: "PUT", body: JSON.stringify(body), headers });

/** A POST whose answer is a file (the encrypted backup), with the name the server suggests. */
async function download(path: string, body: unknown, headers: HeadersInit): Promise<{ blob: Blob; filename: string }> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection and try again.");
  }
  if (!response.ok) {
    const parsed: unknown = await response.json().catch(() => null);
    throw new ApiError(response.status, describeError(response.status, parsed));
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "auib-advisor-backup.aab";
  return { blob: await response.blob(), filename };
}

const course = (code: string) => `/api/v1/admin/courses/${encodeURIComponent(code)}`;
const program = (id: string) => `/api/v1/admin/programs/${encodeURIComponent(id)}`;

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
  gpaPlan: (student: StudentIn, courses: ExpectedGrade[], target: number | null) =>
    post<GpaPlan>("/api/v1/planner/gpa", { ...student, courses, target }),
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

    courses: (token: string, show: string, q: string, offset = 0) =>
      request<AdminCourseList>(
        `/api/v1/admin/courses?${new URLSearchParams({ show, q, offset: String(offset), limit: "50" })}`,
        { headers: bearer(token) },
      ),
    course: (token: string, code: string) => request<AdminCourse>(course(code), { headers: bearer(token) }),
    createCourse: (token: string, body: CourseCreate) =>
      post<AdminCourse>("/api/v1/admin/courses", body, bearer(token)),
    updateCourse: (token: string, code: string, body: CourseFields) =>
      put<AdminCourse>(course(code), body, bearer(token)),
    revertCourse: (token: string, code: string) =>
      request<AdminCourse>(`${course(code)}/revert`, { method: "POST", headers: bearer(token) }),
    hideCourse: (token: string, code: string, hidden: boolean) =>
      put<AdminCourseSummary>(`${course(code)}/hidden`, { hidden }, bearer(token)),
    addRule: (token: string, code: string, kind: string, rule: string, note: string | null) =>
      post<AdminRule>(`${course(code)}/rules`, { kind, rule, note }, bearer(token)),
    deleteRule: (token: string, id: number) =>
      request<null>(`/api/v1/admin/rules/${id}`, { method: "DELETE", headers: bearer(token) }),
    bulkCourses: (token: string, body: TableUpload) =>
      post<CourseBulk>("/api/v1/admin/courses/bulk", body, bearer(token)),

    programs: (token: string) => request<AdminProgramSummary[]>("/api/v1/admin/programs", { headers: bearer(token) }),
    program: (token: string, id: string) => request<AdminProgram>(program(id), { headers: bearer(token) }),
    checkProgram: (token: string, draft: ProgramDraft) =>
      post<ProgramCheck>("/api/v1/admin/programs/check", draft, bearer(token)),
    createProgram: (token: string, draft: ProgramDraft) =>
      post<ProgramSave>("/api/v1/admin/programs", draft, bearer(token)),
    updateProgram: (token: string, draft: ProgramDraft) =>
      put<ProgramSave>(program(draft.id), draft, bearer(token)),
    hideProgram: (token: string, id: string, hidden: boolean) =>
      put<AdminProgramSummary>(`${program(id)}/hidden`, { hidden }, bearer(token)),

    schedules: (token: string) => request<ScheduleSummary[]>("/api/v1/admin/schedules", { headers: bearer(token) }),
    schedule: (token: string, year: number, season: string) =>
      request<Schedule>(`/api/v1/admin/schedules/${year}/${season.toLowerCase()}`, { headers: bearer(token) }),
    uploadSchedule: (token: string, body: TableUpload & { term: string }) =>
      post<ScheduleUpload>("/api/v1/admin/schedules", body, bearer(token)),
    deleteSchedule: (token: string, year: number, season: string) =>
      request<null>(`/api/v1/admin/schedules/${year}/${season.toLowerCase()}`, {
        method: "DELETE",
        headers: bearer(token),
      }),

    backup: (token: string, passphrase: string) => download("/api/v1/admin/backup", { passphrase }, bearer(token)),
    checkRestore: (token: string, backup_base64: string, passphrase: string) =>
      post<BackupCheck>("/api/v1/admin/restore/check", { backup_base64, passphrase }, bearer(token)),
    restore: (token: string, backup_base64: string, passphrase: string) =>
      post<RestoreResult>("/api/v1/admin/restore", { backup_base64, passphrase, confirm: "RESTORE" }, bearer(token)),
  },
};
