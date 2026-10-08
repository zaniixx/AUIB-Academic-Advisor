"""Request and response shapes. Inputs are strictly bounded: every list and string has a limit."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.codes import normalize_code
from app.domain.planner import Pace
from app.domain.recommend import GOALS, INTERESTS, Workload
from app.domain.record import AttemptStatus
from app.domain.terms import Term
from app.domain.whatif import ChangeAction

CourseCode = Annotated[str, Field(min_length=5, max_length=16, examples=["CSC 231"])]
TermText = Annotated[str, Field(min_length=6, max_length=40, examples=["Fall 2027", "2027/2028 Fall"])]
_INTEREST_IDS = {interest.id for interest in INTERESTS}
_GOAL_IDS = {goal.id for goal in GOALS}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _code(value: str) -> str:
    code = normalize_code(value)
    if code is None:
        raise ValueError("Not a course code like 'CSC 231'")
    return code


def _term(value: str | None) -> str | None:
    if value is not None and Term.parse(value) is None:
        raise ValueError("Not a term like 'Fall 2027'")
    return value


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class AttemptIn(StrictModel):
    code: CourseCode
    status: AttemptStatus
    term: TermText | None = None
    grade: str | None = Field(default=None, max_length=4)
    units: float | None = Field(default=None, ge=0, le=30)

    _check_code = field_validator("code")(_code)
    _check_term = field_validator("term")(_term)


class LockIn(StrictModel):
    code: CourseCode
    term: TermText

    _check_code = field_validator("code")(_code)
    _check_term = field_validator("term")(_term)


class PreferencesIn(StrictModel):
    preferred_units: float = Field(default=15, ge=3, le=21)
    max_units: float = Field(default=18, ge=3, le=21)
    pace: Pace = Pace.ON_TIME
    include_summer: bool = False
    summer_max_units: float = Field(default=6, ge=0, le=12)
    start_term: TermText | None = None
    locks: list[LockIn] = Field(default_factory=list, max_length=60)
    exclude: list[CourseCode] = Field(default_factory=list, max_length=100)
    include: list[CourseCode] = Field(default_factory=list, max_length=60)
    interests: list[str] = Field(default_factory=list, max_length=len(INTERESTS))
    goal: str | None = Field(default=None, max_length=40)
    workload: Workload = Workload.BALANCED

    _check_start = field_validator("start_term")(_term)

    @field_validator("exclude", "include")
    @classmethod
    def _codes(cls, values: list[str]) -> list[str]:
        return [_code(v) for v in values]

    @field_validator("interests")
    @classmethod
    def _interests(cls, values: list[str]) -> list[str]:
        unknown = set(values) - _INTEREST_IDS
        if unknown:
            raise ValueError("Unknown interest; see /api/v1/meta for the list")
        return values

    @field_validator("goal")
    @classmethod
    def _goal(cls, value: str | None) -> str | None:
        if value is not None and value not in _GOAL_IDS:
            raise ValueError("Unknown goal; see /api/v1/meta for the list")
        return value


class StudentIn(StrictModel):
    """Everything the planner needs. Nothing here is stored (F11.5)."""

    program_id: str = Field(min_length=2, max_length=64)
    minor_id: str | None = Field(default=None, max_length=64)
    attempts: list[AttemptIn] = Field(default_factory=list, max_length=300)
    preferences: PreferencesIn = Field(default_factory=PreferencesIn)


class ChangeIn(StrictModel):
    code: CourseCode
    action: ChangeAction

    _check_code = field_validator("code")(_code)


class WhatIfIn(StudentIn):
    change: ChangeIn


class HistoryParseIn(StrictModel):
    text: str = Field(max_length=300_000)


class RuleUpdateIn(StrictModel):
    rule: str = Field(max_length=2000, description="Rule in the admin rule language, or NONE")
    note: str | None = Field(default=None, max_length=1000)


class RuleCheckIn(StrictModel):
    rule: str = Field(max_length=2000)


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


class TermOut(BaseModel):
    label: str
    year: int
    season: Literal["Spring", "Summer", "Fall"]


class CourseRef(BaseModel):
    code: str
    title: str
    units: float


class OptionOut(BaseModel):
    id: str
    label: str


class MetaOut(BaseModel):
    version: str
    catalog_revision: int
    interests: list[OptionOut]
    goals: list[OptionOut]
    workloads: list[str]
    paces: list[str]
    standing_credits: dict[str, int]
    defaults: dict[str, Any]
    assumptions: list[str]
    disclaimer: str


class ProgramSummaryOut(BaseModel):
    id: str
    name: str
    kind: str
    catalog_year: str | None
    total_units: float
    source: str | None
    source_date: str | None


class GroupOut(BaseModel):
    key: str
    title: str
    label: str
    role: str
    units_required: float
    requires_all: bool
    courses: list[CourseRef]
    children: list[GroupOut]


class ProgramDetailOut(ProgramSummaryOut):
    root: GroupOut


class GatewayOut(BaseModel):
    course: CourseRef
    dependents: int
    direct_dependents: list[str]


class InsightsOut(BaseModel):
    gateways: list[GatewayOut]
    longest_chain: list[CourseRef]


class RuleOut(BaseModel):
    kind: str
    english: str
    rule: str
    source_text: str
    status: str
    reviewed: bool
    overridden: bool


class CourseOut(CourseRef):
    description: str
    component: str | None
    notices: list[str]
    offered_terms: list[str] | None = Field(
        description="Seasons it runs in; null means every Fall and Spring"
    )
    rules: list[RuleOut]
    unlocks: list[CourseRef]
    groups: list[dict[str, str]]


class CourseListOut(BaseModel):
    total: int
    courses: list[CourseRef]


class HistoryRowOut(BaseModel):
    code: str
    title: str | None
    term: str | None
    grade: str | None
    units: float | None
    status: AttemptStatus | None
    sis_status: str | None
    line: int
    issues: list[str]


class UnreadLineOut(BaseModel):
    line: int
    text: str
    reason: str


class HistoryParseOut(BaseModel):
    rows: list[HistoryRowOut]
    unread: list[UnreadLineOut]
    ignored_line_count: int
    duplicates_removed: int


class CountedCourseOut(BaseModel):
    code: str
    title: str
    units: float
    state: Literal["completed", "in_progress", "planned"]


class GroupProgressOut(BaseModel):
    key: str
    label: str
    role: str
    units_required: float
    completed: float
    in_progress: float
    planned: float
    remaining: float
    courses: list[CountedCourseOut]
    children: list[GroupProgressOut]


class LeftItemOut(BaseModel):
    group_key: str
    group_label: str
    units_needed: float
    required_courses: list[CourseRef]
    options: list[CourseRef]
    open_pool: bool


class ProgressOut(BaseModel):
    percent_complete: float
    completed_units: float
    in_progress_units: float
    root: GroupProgressOut
    not_counted: list[CourseRef]
    whats_left: list[LeftItemOut]


class EligibleOut(BaseModel):
    course: CourseRef
    group_key: str
    group_label: str
    unlocks: int
    advisories: list[str]
    take_with: list[str]


class PlanItemOut(BaseModel):
    kind: Literal["course", "slot"]
    key: str
    code: str | None
    title: str
    units: float
    reason: str
    group_key: str | None
    group_label: str | None
    locked: bool
    unlocks: int
    advisories: list[str]
    suggestions: list[CourseRef]
    alternatives: list[CourseRef] = Field(
        description="Courses that could replace this one in the same term: same requirement, offered then, "
        "prerequisites done in earlier terms, corequisites in the same term"
    )


class PlannedTermOut(BaseModel):
    term: TermOut
    units: float
    items: list[PlanItemOut]


class IssueOut(BaseModel):
    severity: Literal["warning", "info"]
    message: str
    code: str | None


class CatalogInfoOut(BaseModel):
    program_id: str
    program_name: str
    catalog_year: str | None
    source: str | None
    source_date: str | None
    revision: int


class MinorPlanOut(BaseModel):
    """The minor the student chose: its requirements now and once the plan is done.

    A course can count toward the major and the minor at the same time.
    """

    program_id: str
    name: str
    total_units: float
    source: str | None
    source_date: str | None
    progress: ProgressOut
    progress_with_plan: GroupProgressOut


class PlanOut(BaseModel):
    start_term: TermOut
    graduation_term: TermOut | None
    on_time_term: TermOut | None
    terms: list[PlannedTermOut]
    issues: list[IssueOut]
    unscheduled: list[PlanItemOut]
    critical_chain: list[CourseRef]
    progress: ProgressOut
    progress_with_plan: GroupProgressOut
    eligible_next_term: list[EligibleOut]
    degree_map: DegreeMapOut
    gpa: GpaOut | None = Field(description="Null until the student has a graded course")
    minor: MinorPlanOut | None = Field(default=None, description="Null when no minor was chosen")
    catalog: CatalogInfoOut
    assumptions: list[str]
    disclaimer: str


class MapColumnOut(BaseModel):
    label: str
    kind: Literal["completed", "current", "planned", "unscheduled"]


class MapNodeOut(BaseModel):
    key: str
    code: str | None
    title: str
    units: float
    status: Literal["done", "in_progress", "planned", "choice", "blocked"]
    column: int
    group_label: str | None


class MapEdgeOut(BaseModel):
    source: str
    target: str


class DegreeMapOut(BaseModel):
    """Every course on the student's path by term, with prerequisite links (F5.1)."""

    columns: list[MapColumnOut]
    nodes: list[MapNodeOut]
    edges: list[MapEdgeOut]


class TermGpaOut(BaseModel):
    term: TermOut
    gpa: float
    units: float


class RetakeOut(BaseModel):
    course: CourseRef
    grade: str
    with_a: float = Field(description="CGPA if the retake earns an A")
    with_b: float = Field(description="CGPA if the retake earns a B")
    in_plan: bool = Field(description="Already in the plan (a failed course that must be retaken anyway)")


class GpaOut(BaseModel):
    """Cumulative GPA, the last graded term's GPA and the retakes that would raise the CGPA most (F7)."""

    cumulative: float
    units: float
    last_term: TermGpaOut | None
    retakes: list[RetakeOut]
    assumptions: list[str]


class ShiftOut(BaseModel):
    code: str
    title: str
    before: TermOut | None
    after: TermOut | None


class WhatIfOut(BaseModel):
    change: ChangeIn
    terms_later: int
    before_graduation: TermOut | None
    after_graduation: TermOut | None
    shifts: list[ShiftOut]
    plan: PlanOut


class SuggestionOut(BaseModel):
    course: CourseRef
    score: float
    reasons: list[str]
    eligible_now: bool
    missing: list[str]


class GroupSuggestionsOut(BaseModel):
    group_key: str
    group_label: str
    units_needed: float
    suggestions: list[SuggestionOut]


class RecommendationsOut(BaseModel):
    groups: list[GroupSuggestionsOut]


class AdminRuleOut(BaseModel):
    id: int
    course_code: str
    course_title: str
    kind: str
    source_text: str
    status: str
    unparsed_text: str
    parsed_rule: str
    parsed_english: str
    override_rule: str | None
    override_note: str | None
    effective_rule: str
    effective_english: str
    reviewed: bool
    reviewed_by: str | None
    reviewed_at: datetime | None
    source_changed: bool


class AdminRuleListOut(BaseModel):
    total: int
    counts: dict[str, int]
    rules: list[AdminRuleOut]


class RuleCheckOut(BaseModel):
    valid: bool
    rule: str | None = None
    english: str | None = None
    error: str | None = None
    position: int | None = None
    unknown_courses: list[str] = Field(default_factory=list)


class ImportRunOut(BaseModel):
    id: int
    program_id: str
    started_at: datetime
    status: str
    published: bool
    actor: str
    report: dict[str, Any]


class AuditOut(BaseModel):
    id: int
    at: datetime
    actor: str
    action: str
    target: str
    detail: dict[str, Any]


class HealthOut(BaseModel):
    status: Literal["ok"]


class ReadyOut(BaseModel):
    status: Literal["ready"]
    database: Literal["ok"]
    catalog_revision: int
    programs: int
    today: date
