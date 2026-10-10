"""Request and response shapes. Inputs are strictly bounded: every list and string has a limit."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.codes import normalize_code
from app.domain.interests import GOALS, INTERESTS, PLANS_BY_ID, TRAITS, TRAITS_BY_ID
from app.domain.planner import Pace
from app.domain.recommend import Workload
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
    built_terms: list[TermText] = Field(
        default_factory=list,
        max_length=36,
        description="Terms the student finished building (F1.9): they hold the student's locked courses "
        "and nothing else",
    )
    exclude: list[CourseCode] = Field(default_factory=list, max_length=100)
    include: list[CourseCode] = Field(default_factory=list, max_length=60)
    interests: list[str] = Field(default_factory=list, max_length=len(INTERESTS))
    goal: str | None = Field(default=None, max_length=40)
    workload: Workload = Workload.BALANCED
    plans: str | None = Field(
        default=None, max_length=40, description="What the student plans after graduating (F2.1)"
    )
    avoid: list[str] = Field(
        default_factory=list,
        max_length=len(TRAITS),
        description="Course traits the student would rather avoid, such as essays (F2.1)",
    )

    _check_start = field_validator("start_term")(_term)

    @field_validator("built_terms")
    @classmethod
    def _built(cls, values: list[str]) -> list[str]:
        for value in values:
            _term(value)
        return values

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

    @field_validator("plans")
    @classmethod
    def _plans(cls, value: str | None) -> str | None:
        if value is not None and value not in PLANS_BY_ID:
            raise ValueError("Unknown plan; see /api/v1/meta for the list")
        return value

    @field_validator("avoid")
    @classmethod
    def _avoid(cls, values: list[str]) -> list[str]:
        if set(values) - set(TRAITS_BY_ID):
            raise ValueError("Unknown course trait; see /api/v1/meta for the list")
        return values

    @field_validator("goal")
    @classmethod
    def _goal(cls, value: str | None) -> str | None:
        if value is not None and value not in _GOAL_IDS:
            raise ValueError("Unknown goal; see /api/v1/meta for the list")
        return value


class PlanChoicesIn(StrictModel):
    """The student's programs and plan choices: everything the planner needs but their courses."""

    program_id: str = Field(min_length=2, max_length=64)
    minor_id: str | None = Field(default=None, max_length=64)
    preferences: PreferencesIn = Field(default_factory=PreferencesIn)
    entry_term: TermText | None = Field(
        default=None,
        description="The term the student joined AUIB; worked out from the course history if empty",
    )
    program_version: str | None = Field(
        default=None,
        max_length=64,
        description="A specific version of the major, when the registrar approved a move to it (F0.4)",
    )

    _check_entry = field_validator("entry_term")(_term)


class StudentIn(PlanChoicesIn):
    """Everything the planner needs. Nothing here is stored (F11.5)."""

    attempts: list[AttemptIn] = Field(default_factory=list, max_length=300)


class ScenarioIn(PlanChoicesIn):
    """A plan the student saved to compare (F6.2): its programs and choices, under a name."""

    name: str = Field(min_length=1, max_length=60)


class CompareIn(StrictModel):
    """Plans to compare side by side (F6.2); they share the student's courses."""

    attempts: list[AttemptIn] = Field(default_factory=list, max_length=300)
    scenarios: list[ScenarioIn] = Field(
        min_length=1,
        max_length=4,
        description="The current plan first, then up to 3 saved scenarios; later terms are compared with "
        "the first",
    )


class ProgramChangeIn(StudentIn):
    """The student's plan and the major (and minor) they are thinking of moving to (F6.3)."""

    target_program_id: str = Field(min_length=2, max_length=64)
    target_minor_id: str | None = Field(default=None, max_length=64, description="Null: no minor")


class MoveIn(StudentIn):
    """A planned course the student wants to put in another term (F6.1)."""

    code: CourseCode

    _check_code = field_validator("code")(_code)


GradeLetter = Literal["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]


class ExpectedGradeIn(StrictModel):
    code: CourseCode
    grade: GradeLetter | None = Field(default=None, description="The grade expected; empty if unsure")

    _check_code = field_validator("code")(_code)


class GpaPlanIn(StudentIn):
    """Courses to project (F7.2) and, optionally, a target CGPA to work back from (F7.3)."""

    courses: list[ExpectedGradeIn] = Field(default_factory=list, max_length=40)
    target: float | None = Field(default=None, gt=0, le=4)


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
    plans: list[OptionOut]
    avoid: list[OptionOut]
    workloads: list[str]
    paces: list[str]
    standing_credits: dict[str, int]
    defaults: dict[str, Any]
    assumptions: list[str]
    disclaimer: str


class ProgramVersionOut(BaseModel):
    id: str
    name: str
    catalog_year: str | None
    valid_from: str | None = Field(
        description="The first entry term it applies to; null means from the start"
    )
    applies_to: str = Field(description='Whom it applies to, e.g. "students who joined from Fall 2027 on"')
    in_use: bool = Field(default=False, description="The version this plan follows")


class ProgramSummaryOut(BaseModel):
    id: str
    name: str
    kind: str
    catalog_year: str | None
    total_units: float
    source: str | None
    source_date: str | None
    versions: list[ProgramVersionOut] = Field(
        default_factory=list, description="Every version of the program, oldest first (F0.4)"
    )


class GroupOut(BaseModel):
    key: str
    title: str
    label: str
    role: str
    units_required: float
    requires_all: bool
    courses: list[CourseRef]
    children: list[GroupOut]


class ShowIfOut(BaseModel):
    question: str
    answers: list[str] = Field(description="Ask the question only after one of these answers")


class QuestionOut(BaseModel):
    id: str
    field: Literal["interests", "avoid", "plans", "goal"] = Field(
        description="The preference the answer goes into; two questions can fill interests"
    )
    kind: Literal["single", "multi"]
    title: str
    hint: str
    options: list[OptionOut]
    show_if: ShowIfOut | None


class QuestionsOut(BaseModel):
    program_id: str
    questions: list[QuestionOut]


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


class OfferingOut(BaseModel):
    code: str
    title: str
    section: str
    days: str
    time: str
    instructor: str
    room: str


class TermOfferingsOut(BaseModel):
    term: TermOut
    sections: list[OfferingOut]


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
    offerings: list[TermOfferingsOut] = Field(
        default_factory=list, description="Sections on published schedules, this term onward"
    )


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


_ALSO_LISTED = (
    "Other requirements of the same program that list this course (F1.7). A course counts toward one "
    "requirement only: the first, in SIS order, that still needs it"
)
_ALSO_COUNTS = (
    "Requirements of the student's other program (minor or major) the course counts toward at the same "
    "time, each with the program's name (F1.7)"
)


class CountedCourseOut(BaseModel):
    code: str
    title: str
    units: float
    state: Literal["completed", "in_progress", "planned"]
    also_listed: list[str] = Field(description=_ALSO_LISTED)
    also_counts_toward: list[str] = Field(description=_ALSO_COUNTS)


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
    counts_toward: str | None = Field(
        description="The requirement this course counts toward once the plan is done (F1.7)"
    )
    also_listed: list[str] = Field(description=_ALSO_LISTED)
    also_counts_toward: list[str] = Field(description=_ALSO_COUNTS)


class PlannedTermOut(BaseModel):
    term: TermOut
    units: float
    items: list[PlanItemOut]
    built: bool = Field(description="The student chose this term's courses themselves (F1.9)")
    schedule_published: bool = Field(
        description="True when the courses were checked against the registrar's published schedule for "
        "this term (F1.8); otherwise it is not known yet whether they will be offered"
    )


class IssueOut(BaseModel):
    severity: Literal["warning", "info"]
    message: str
    code: str | None


class CatalogInfoOut(BaseModel):
    program_id: str = Field(description="The version of the major this plan follows")
    program_name: str
    catalog_year: str | None
    source: str | None
    source_date: str | None
    revision: int
    family_id: str = Field(description="The program, whichever version")
    valid_from: str | None
    entry_term: str | None = Field(description="The term the student joined AUIB, as the plan understood it")
    version_choice: Literal["only", "joined", "chosen", "earliest"]
    version_note: str = Field(description="Which requirements apply to this student and why")
    versions: list[ProgramVersionOut]


class MinorPlanOut(BaseModel):
    """The minor the student chose: its requirements now and once the plan is done.

    A course can count toward the major and the minor at the same time.
    """

    program_id: str
    name: str
    total_units: float
    source: str | None
    source_date: str | None
    valid_from: str | None = Field(default=None, description="The minor version's first entry term (F0.4)")
    progress: ProgressOut
    progress_with_plan: GroupProgressOut


class TermChoiceOut(EligibleOut):
    planned_for: TermOut | None = Field(
        description="A later term the plan already has this course in; null when it is not in the plan"
    )


class BuildingOut(BaseModel):
    """The term the student is building now (F1.9)."""

    term: TermOut
    choices: list[TermChoiceOut] = Field(
        description="Courses that could be added besides the ones the plan has in this term: they count "
        "toward an open requirement, run that term and have their prerequisites done in earlier terms"
    )


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
    building: BuildingOut | None = Field(
        default=None, description="The first planned term the student has not built yet (F1.9)"
    )
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


class MoveOptionOut(BaseModel):
    """The course checked in one term (F6.1)."""

    term: TermOut
    valid: bool
    problems: list[str] = Field(description="Why the course cannot go in this term; empty when it can")
    graduation_term: TermOut | None = Field(
        description="Graduation with the course in this term; null when the course does not run then"
    )
    terms_later: int = Field(description="How many terms later graduation moves (negative if earlier)")
    shifts: list[ShiftOut] = Field(description="Every course whose term changes, this one included")


class MoveOptionsOut(BaseModel):
    """Where a planned course can go: every other term of the plan, and the term after it (F6.1)."""

    course: CourseRef
    term: TermOut = Field(description="The term the plan has the course in now")
    graduation_term: TermOut | None
    options: list[MoveOptionOut]


class ScenarioTermOut(BaseModel):
    term: TermOut
    units: float
    built: bool
    courses: list[CourseRef]
    open_choices: list[str] = Field(description="Requirements with a course still to choose in this term")


class ScenarioPlanOut(BaseModel):
    program_name: str
    minor_name: str | None
    catalog_year: str | None
    graduation_term: TermOut | None
    on_time_term: TermOut | None
    semesters_vs_first: int | None = Field(
        description="How many Fall/Spring semesters later than the first scenario it finishes (negative if "
        "earlier); null for the first scenario"
    )
    percent_complete: float
    counted_credits: float = Field(
        description="Completed and in-progress credits that count toward the major"
    )
    credits_left: float
    planned_credits: float
    warnings: int = Field(description="Problems the plan reports, such as courses it could not schedule")
    terms: list[ScenarioTermOut]


class ScenarioOut(BaseModel):
    name: str
    plan: ScenarioPlanOut | None
    error: str | None = Field(
        description="Why the scenario could not be planned, such as a program no longer offered"
    )


class CompareOut(BaseModel):
    scenarios: list[ScenarioOut]


class TransferCourseOut(BaseModel):
    course: CourseRef
    state: Literal["completed", "in_progress"]
    now: str | None = Field(
        description="The requirement it counts toward now; null when it counts toward none"
    )
    after: str | None = Field(description="The requirement it would count toward in the new major")
    after_minor: str | None = Field(description="The requirement it would count toward in the new minor")


class ProgramSideOut(BaseModel):
    program_id: str
    name: str
    minor_name: str | None
    catalog_year: str | None
    total_credits: float
    counted_credits: float = Field(description="Completed and in-progress credits that count toward it")
    credits_left: float
    percent_complete: float
    graduation_term: TermOut | None
    on_time_term: TermOut | None


class ProgramChangeOut(BaseModel):
    """What changing major or minor would do (F6.3)."""

    current: ProgramSideOut
    target: ProgramSideOut
    terms_later: int = Field(
        description="How many terms later the new program finishes (negative if earlier)"
    )
    courses: list[TransferCourseOut]
    lost_credits: float = Field(description="Credits that count now but toward neither new program")
    version_note: str = Field(description="Which requirements of the new major are used, and why")
    notes: list[str]


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


class GpaTargetOut(BaseModel):
    target: float
    status: Literal["met", "reachable", "out_of_reach", "no_courses"] = Field(
        description="met: reached whatever the open courses' grades; out_of_reach: not even with A's"
    )
    average_needed: float | None = Field(description="Grade points per credit the open courses must average")
    grade_needed: str | None = Field(description="The lowest letter grade at or above that average")
    open_credits: float = Field(description="Credits of the courses without an expected grade")
    best_possible: float | None = Field(description="The CGPA with an A in every open course")


class GpaPlanOut(BaseModel):
    current: float | None
    projected: float | None = Field(description="The CGPA with the expected grades; null when none is given")
    courses_gpa: float | None = Field(description="The GPA of the courses with an expected grade alone")
    graded_credits: float
    target: GpaTargetOut | None
    assumptions: list[str]


class HealthOut(BaseModel):
    status: Literal["ok"]


class ReadyOut(BaseModel):
    status: Literal["ready"]
    database: Literal["ok"]
    catalog_revision: int
    programs: int
    today: date
