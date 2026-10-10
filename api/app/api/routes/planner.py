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
from app.domain.planner import (
    Plan,
    PlanOptions,
    build_plan,
    building_term,
    current_progress,
    eligible_next_term,
    term_choices,
)
from app.domain.progress import ProgramProgress
from app.domain.recommend import open_groups, suggest_for_group
from app.domain.record import StudentRecord
from app.domain.requisites import EvalContext
from app.domain.switch import change_program
from app.domain.terms import Term, current_term, first_planning_term, terms_between
from app.domain.whatif import Change, WhatIfError, move_options, what_if

router = APIRouter(prefix="/api/v1", tags=["planner"])


@dataclass(frozen=True)
class Chosen:
    """The student's major and minor, in the versions that apply to them (F0.4)."""

    program: Program
    minor: Program | None
    version: VersionChoice
    entry_source: str  # "given" (the student said), "history" (first term in it) or "start"


def _entry(student: s.PlanChoicesIn, record: StudentRecord, today: date) -> tuple[Term, str]:
    """When the student joined AUIB: as they said, else their first term on record, else next term."""
    if student.entry_term and (given := Term.parse(student.entry_term)):
        return given, "given"
    if (first := record.first_term()) is not None:
        return first, "history"
    return first_planning_term(today, include_summer=False), "start"


def _programs(catalog: Catalog, student: s.PlanChoicesIn, record: StudentRecord, today: date) -> Chosen:
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


def _building(
    chosen: Chosen, catalog: Catalog, record: StudentRecord, options: PlanOptions, plan: Plan
) -> s.BuildingOut | None:
    """The term the student is building and what they could add to it (F1.9)."""
    planned = building_term(plan)
    if planned is None:
        return None
    found = term_choices(chosen.program, catalog, record, options, plan, planned, chosen.minor)
    return convert.building_out(planned, found, plan, catalog)


def _current_progress(program: Program, catalog: Catalog, record: StudentRecord) -> ProgramProgress:
    return current_progress(program, catalog, record)


@router.post("/history/parse", summary="Read a pasted SIS Course History page (F11.3)")
def parse_history(body: s.HistoryParseIn, catalog: CatalogDep) -> s.HistoryParseOut:
    titles = {code: course.title for code, course in catalog.courses.items()}
    return convert.history_out(parse_course_history(body.text, titles))


@router.post("/planner/progress", summary="Progress per requirement and what is left (F1.2, F4)")
def progress(student: s.StudentIn, catalog: CatalogDep, today: TodayDep) -> s.ProgressOut:
    record = convert.record_from(student.attempts)
    program = _programs(catalog, student, record, today).program
    return convert.progress_out(_current_progress(program, catalog, record), record, catalog)


@router.post("/planner/plan", summary="A term-by-term plan to graduation (F1.3, F1.4, F1.6, F1.9)")
def plan(student: s.StudentIn, catalog: CatalogDep, today: TodayDep) -> s.PlanOut:
    record = convert.record_from(student.attempts)
    chosen = _programs(catalog, student, record, today)
    program, minor = chosen.program, chosen.minor
    options = convert.options_from(student.preferences, program)
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
        _building(chosen, catalog, record, options, result),
    )


@router.post("/planner/what-if", summary="What dropping or delaying a course does to graduation (F1.5)")
def plan_what_if(body: s.WhatIfIn, catalog: CatalogDep, today: TodayDep) -> s.WhatIfOut:
    record = convert.record_from(body.attempts)
    chosen = _programs(catalog, body, record, today)
    program, minor = chosen.program, chosen.minor
    options = convert.options_from(body.preferences, program)
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
        shifts=[convert.shift_out(shift) for shift in result.shifts],
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


@router.post(
    "/planner/move-options",
    summary="Where a planned course can be moved, and what each move does to graduation (F6.1)",
)
def plan_move_options(body: s.MoveIn, catalog: CatalogDep, today: TodayDep) -> s.MoveOptionsOut:
    record = convert.record_from(body.attempts)
    chosen = _programs(catalog, body, record, today)
    options = convert.options_from(body.preferences, chosen.program)
    try:
        found = move_options(chosen.program, catalog, record, options, body.code, today, chosen.minor)
    except WhatIfError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    return convert.move_choices_out(found, body.code, catalog)


@router.post("/planner/compare", summary="Compare the current plan with up to 3 saved scenarios (F6.2)")
def compare(body: s.CompareIn, catalog: CatalogDep, today: TodayDep) -> s.CompareOut:
    record = convert.record_from(body.attempts)
    first: Plan | None = None
    results: list[s.ScenarioOut] = []
    for index, scenario in enumerate(body.scenarios):
        try:
            chosen = _programs(catalog, scenario, record, today)
        except HTTPException as error:
            # A scenario saved for a program that is no longer offered should not hide the others.
            results.append(s.ScenarioOut(name=scenario.name, plan=None, error=str(error.detail)))
            continue
        options = convert.options_from(scenario.preferences, chosen.program)
        plan = build_plan(chosen.program, catalog, record, options, today, chosen.minor, alternatives=False)
        if index == 0:
            first = plan
        versus = (
            terms_between(first.graduation_term, plan.graduation_term, include_summer=False)
            if first is not None and index > 0
            else None
        )
        current = _current_progress(chosen.program, catalog, record)
        summary = convert.scenario_plan_out(plan, chosen.program, chosen.minor, current, catalog, versus)
        results.append(s.ScenarioOut(name=scenario.name, plan=summary, error=None))
    return s.CompareOut(scenarios=results)


@router.post("/planner/change-program", summary="What changing major or minor would do (F6.3)")
def plan_change_program(body: s.ProgramChangeIn, catalog: CatalogDep, today: TodayDep) -> s.ProgramChangeOut:
    record = convert.record_from(body.attempts)
    chosen = _programs(catalog, body, record, today)
    target_choice = body.model_copy(
        update={
            "program_id": body.target_program_id,
            "minor_id": body.target_minor_id,
            "program_version": None,
        }
    )
    target = _programs(catalog, target_choice, record, today)
    options = convert.options_from(body.preferences, chosen.program)
    result = change_program(
        chosen.program, target.program, catalog, record, options, today, chosen.minor, target.minor
    )
    return convert.program_change_out(
        result,
        chosen.program,
        chosen.minor,
        target.program,
        target.minor,
        catalog,
        convert.version_note(target.version, target.entry_source),
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
