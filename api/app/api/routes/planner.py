"""Planning endpoints.

They are stateless: the student's courses arrive with each request and are never stored (F11.5).
"""

from fastapi import APIRouter, HTTPException, status

from app.api import convert
from app.api import schemas as s
from app.api.deps import CatalogDep, TodayDep, published_program
from app.domain.catalog import Catalog, Program
from app.domain.history import parse_course_history
from app.domain.planner import build_plan, eligible_next_term
from app.domain.progress import CourseState, ProgramProgress, allocate
from app.domain.recommend import open_groups, suggest_for_group
from app.domain.record import StudentRecord
from app.domain.requisites import EvalContext
from app.domain.terms import current_term
from app.domain.whatif import Change, WhatIfError, what_if

router = APIRouter(prefix="/api/v1", tags=["planner"])


def _programs(catalog: Catalog, student: s.StudentIn) -> tuple[Program, Program | None]:
    """The student's major and, if they chose one, their minor (both must be published)."""
    program = published_program(catalog, student.program_id)
    if program.kind != "major":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose a major as the program")
    if not student.minor_id:
        return program, None
    minor = published_program(catalog, student.minor_id)
    if minor.kind != "minor":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose a minor as the minor")
    return program, minor


def _current_progress(program: Program, catalog: Catalog, record: StudentRecord) -> ProgramProgress:
    courses = [(c, record.units_of(c, catalog), CourseState.COMPLETED) for c in sorted(record.completed)]
    courses += [(c, record.units_of(c, catalog), CourseState.IN_PROGRESS) for c in sorted(record.in_progress)]
    return allocate(program, catalog, courses)


@router.post("/history/parse", summary="Read a pasted SIS Course History page (F11.3)")
def parse_history(body: s.HistoryParseIn, catalog: CatalogDep) -> s.HistoryParseOut:
    titles = {code: course.title for code, course in catalog.courses.items()}
    return convert.history_out(parse_course_history(body.text, titles))


@router.post("/planner/progress", summary="Progress per requirement and what is left (F1.2, F4)")
def progress(student: s.StudentIn, catalog: CatalogDep) -> s.ProgressOut:
    program, _minor = _programs(catalog, student)
    record = convert.record_from(student.attempts)
    return convert.progress_out(_current_progress(program, catalog, record), record, catalog)


@router.post("/planner/plan", summary="A term-by-term plan to graduation (F1.3, F1.4, F1.6)")
def plan(student: s.StudentIn, catalog: CatalogDep, today: TodayDep) -> s.PlanOut:
    program, minor = _programs(catalog, student)
    record = convert.record_from(student.attempts)
    options = convert.options_from(student.preferences)
    result = build_plan(program, catalog, record, options, today, minor)
    eligible = eligible_next_term(program, catalog, record, options, result.start_term, minor)
    current = _current_progress(program, catalog, record)
    minor_current = _current_progress(minor, catalog, record) if minor else None
    return convert.plan_out(
        result, program, catalog, record, current, eligible, current_term(today), minor, minor_current
    )


@router.post("/planner/what-if", summary="What dropping or delaying a course does to graduation (F1.5)")
def plan_what_if(body: s.WhatIfIn, catalog: CatalogDep, today: TodayDep) -> s.WhatIfOut:
    program, minor = _programs(catalog, body)
    record = convert.record_from(body.attempts)
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
        ),
    )


@router.post("/planner/recommendations", summary="Ranked electives for each open requirement (F2.2)")
def recommendations(student: s.StudentIn, catalog: CatalogDep) -> s.RecommendationsOut:
    program, minor = _programs(catalog, student)
    record = convert.record_from(student.attempts)
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
