"""Planning endpoints.

They are stateless: the student's courses arrive with each request and are never stored (F11.5).
"""

from dataclasses import dataclass
from datetime import date

from fastapi import APIRouter, HTTPException, status

from app.api import convert
from app.api import schemas as s
from app.api.deps import CatalogDep, TodayDep
from app.domain.catalog import Catalog, Program, VersionChoice, VersionError, choose_version
from app.domain.gpa import GPA_ASSUMPTIONS, gpa_summary, grades_for_target, project_gpa
from app.domain.history import parse_course_history
from app.domain.planner import build_plan, eligible_next_term
from app.domain.progress import CourseState, ProgramProgress, allocate
from app.domain.recommend import open_groups, suggest_for_group
from app.domain.record import StudentRecord
from app.domain.requisites import EvalContext
from app.domain.terms import Term, current_term, first_planning_term
from app.domain.whatif import Change, WhatIfError, what_if

router = APIRouter(prefix="/api/v1", tags=["planner"])


@dataclass(frozen=True)
class Chosen:
    """The student's major and minor, in the versions that apply to them (F0.4)."""

    program: Program
    minor: Program | None
    version: VersionChoice
    entry_source: str  # "given" (the student said), "history" (first term in it) or "start"


def _entry(student: s.StudentIn, record: StudentRecord, today: date) -> tuple[Term, str]:
    """When the student joined AUIB: as they said, else their first term on record, else next term."""
    if student.entry_term and (given := Term.parse(student.entry_term)):
        return given, "given"
    if (first := record.first_term()) is not None:
        return first, "history"
    return first_planning_term(today, include_summer=False), "start"


def _programs(catalog: Catalog, student: s.StudentIn, record: StudentRecord, today: date) -> Chosen:
    """The student's major and, if they chose one, their minor, in the versions that apply to them."""
    entry, source = _entry(student, record, today)
    try:
        version = choose_version(catalog, student.program_id, entry, student.program_version)
        minor = choose_version(catalog, student.minor_id, entry).program if student.minor_id else None
    except VersionError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    if version.program.kind != "major":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose a major as the program")
    if minor is not None and minor.kind != "minor":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose a minor as the minor")
    return Chosen(version.program, minor, version, source)


def _current_progress(program: Program, catalog: Catalog, record: StudentRecord) -> ProgramProgress:
    courses = [(c, record.units_of(c, catalog), CourseState.COMPLETED) for c in sorted(record.completed)]
    courses += [(c, record.units_of(c, catalog), CourseState.IN_PROGRESS) for c in sorted(record.in_progress)]
    return allocate(program, catalog, courses)


@router.post("/history/parse", summary="Read a pasted SIS Course History page (F11.3)")
def parse_history(body: s.HistoryParseIn, catalog: CatalogDep) -> s.HistoryParseOut:
    titles = {code: course.title for code, course in catalog.courses.items()}
    return convert.history_out(parse_course_history(body.text, titles))


@router.post("/planner/progress", summary="Progress per requirement and what is left (F1.2, F4)")
def progress(student: s.StudentIn, catalog: CatalogDep, today: TodayDep) -> s.ProgressOut:
    record = convert.record_from(student.attempts)
    program = _programs(catalog, student, record, today).program
    return convert.progress_out(_current_progress(program, catalog, record), record, catalog)


@router.post("/planner/plan", summary="A term-by-term plan to graduation (F1.3, F1.4, F1.6)")
def plan(student: s.StudentIn, catalog: CatalogDep, today: TodayDep) -> s.PlanOut:
    record = convert.record_from(student.attempts)
    chosen = _programs(catalog, student, record, today)
    program, minor = chosen.program, chosen.minor
    options = convert.options_from(student.preferences)
    result = build_plan(program, catalog, record, options, today, minor)
    eligible = eligible_next_term(program, catalog, record, options, result.start_term, minor)
    current = _current_progress(program, catalog, record)
    minor_current = _current_progress(minor, catalog, record) if minor else None
    return convert.plan_out(
        result,
        program,
        catalog,
        record,
        current,
        eligible,
        current_term(today),
        minor,
        minor_current,
        chosen.version,
        chosen.entry_source,
    )


@router.post("/planner/what-if", summary="What dropping or delaying a course does to graduation (F1.5)")
def plan_what_if(body: s.WhatIfIn, catalog: CatalogDep, today: TodayDep) -> s.WhatIfOut:
    record = convert.record_from(body.attempts)
    chosen = _programs(catalog, body, record, today)
    program, minor = chosen.program, chosen.minor
    options = convert.options_from(body.preferences)
    try:
        result = what_if(
            program, catalog, record, options, Change(body.change.code, body.change.action), today, minor
        )
    except WhatIfError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    changed_record = convert.record_from(
        [a for a in body.attempts if not (a.code == body.change.code and a.status == "in_progress")]
    )
    eligible = eligible_next_term(program, catalog, changed_record, options, result.after.start_term, minor)
    current = _current_progress(program, catalog, changed_record)
    minor_current = _current_progress(minor, catalog, changed_record) if minor else None
    return s.WhatIfOut(
        change=body.change,
        terms_later=result.terms_later,
        before_graduation=convert.term_out(result.before.graduation_term),
        after_graduation=convert.term_out(result.after.graduation_term),
        shifts=[
            s.ShiftOut(
                code=shift.code,
                title=shift.title,
                before=convert.term_out(shift.before),
                after=convert.term_out(shift.after),
            )
            for shift in result.shifts
        ],
        plan=convert.plan_out(
            result.after,
            program,
            catalog,
            changed_record,
            current,
            eligible,
            current_term(today),
            minor,
            minor_current,
            chosen.version,
            chosen.entry_source,
        ),
    )


@router.post("/planner/recommendations", summary="Ranked electives for each open requirement (F2.2)")
def recommendations(student: s.StudentIn, catalog: CatalogDep, today: TodayDep) -> s.RecommendationsOut:
    record = convert.record_from(student.attempts)
    chosen = _programs(catalog, student, record, today)
    program, minor = chosen.program, chosen.minor
    options = convert.options_from(student.preferences)
    context = EvalContext(
        completed=record.have,
        credits=record.completed_units(catalog) + record.in_progress_units(catalog),
    )
    exclude = set(record.have) | set(options.exclude)
    groups = []
    for each in (program, minor):
        if each is None:
            continue
        current = _current_progress(each, catalog, record)
        for group in open_groups(each, catalog):
            needed = current.leaves[group.key].remaining_after_current
            if needed <= 0:
                continue
            found = suggest_for_group(group, needed, catalog, options.preferences, context, exclude, limit=6)
            groups.append(convert.suggestions_out(found, catalog))
    return s.RecommendationsOut(groups=groups)


@router.post(
    "/planner/gpa",
    summary="Project the CGPA from expected grades, or the grades a target CGPA needs (F7.2, F7.3)",
)
def gpa_plan(body: s.GpaPlanIn, catalog: CatalogDep) -> s.GpaPlanOut:
    record = convert.record_from(body.attempts)
    expected = {course.code: course.grade for course in body.courses if course.grade}
    current = gpa_summary(record, catalog)
    projection = project_gpa(record, catalog, expected)
    target = None
    if body.target is not None:
        found = grades_for_target(record, catalog, expected, [c.code for c in body.courses], body.target)
        target = s.GpaTargetOut(
            target=found.target,
            status=found.status,
            average_needed=found.average_needed,
            grade_needed=found.grade_needed,
            open_credits=found.open_units,
            best_possible=found.best_possible,
        )
    return s.GpaPlanOut(
        current=current.cumulative if current else None,
        projected=projection.cumulative if expected else None,
        courses_gpa=projection.courses_gpa,
        graded_credits=projection.units,
        target=target,
        assumptions=list(GPA_ASSUMPTIONS),
    )
