"""Turn requests into domain objects and domain results into responses."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace

from app.api import schemas as s
from app.domain.catalog import Catalog, Group, Program, VersionChoice, group_requires_all, version_range
from app.domain.gpa import GPA_ASSUMPTIONS, GpaSummary, gpa_summary
from app.domain.history import HistoryParseResult
from app.domain.journey import DegreeMap, degree_map
from app.domain.planner import EligibleCourse, Lock, Plan, PlanItem, PlannedTerm, PlanOptions
from app.domain.progress import (
    CountedCourse,
    CourseFlags,
    CourseState,
    GroupProgress,
    ProgramProgress,
    course_flags,
    whats_left,
    with_program,
)
from app.domain.recommend import GroupSuggestions, Preferences
from app.domain.record import Attempt, StudentRecord, build_record
from app.domain.requisites import DEFAULT_STANDING_CREDITS
from app.domain.switch import ProgramChange, counted_units, units_left
from app.domain.terms import Term
from app.domain.whatif import MoveChoices, Shift
from app.models import TermOfferingRow

DISCLAIMER = (
    "This plan is a planning aid, not an official degree audit. The registrar's audit in SIS is "
    "authoritative; confirm your plan with your academic advisor."
)
ASSUMPTIONS = [
    "In-progress courses are assumed to be passed.",
    "Class standing uses 30, 60 and 90 completed credits for sophomore, junior and senior; AUIB has not "
    "confirmed these thresholds yet.",
    "Courses run every Fall and Spring unless the catalog says otherwise; internships run in summer only, so "
    "they are planned in a summer term even when you do not plan other summer courses.",
    "Summer terms are limited to the summer credit cap; summer offerings are not confirmed.",
    "Grades from A+ to D- pass a course; minimum-grade rules for prerequisites are not modelled yet.",
    "A course counts toward the first requirement group, in SIS order, that still needs it.",
]


def plan_assumptions(catalog: Catalog) -> list[str]:
    """The fixed assumptions, plus which terms were checked against a published schedule."""
    if not catalog.schedules:
        return ASSUMPTIONS
    labels = ", ".join(term.label for term in sorted(catalog.schedules))
    return [
        *ASSUMPTIONS,
        f"Courses for {labels} come from the published course schedule; other terms assume each course "
        "runs in its usual season.",
    ]


def term_out(term: Term | None) -> s.TermOut | None:
    if term is None:
        return None
    return s.TermOut(label=term.label, year=term.year, season=term.season.label)


def required_term(term: Term) -> s.TermOut:
    out = term_out(term)
    assert out is not None
    return out


def offering_out(row: TermOfferingRow, catalog: Catalog) -> s.OfferingOut:
    return s.OfferingOut(
        code=row.course_code,
        title=catalog.title(row.course_code),
        section=row.section,
        days=row.days,
        time=row.time,
        instructor=row.instructor,
        room=row.room,
    )


def term_offerings_out(
    found: list[tuple[Term, list[TermOfferingRow]]], catalog: Catalog
) -> list[s.TermOfferingsOut]:
    """Sections on published schedules, grouped by term."""
    return [
        s.TermOfferingsOut(term=required_term(term), sections=[offering_out(row, catalog) for row in rows])
        for term, rows in found
    ]


def course_ref(code: str, catalog: Catalog) -> s.CourseRef:
    return s.CourseRef(code=code, title=catalog.title(code), units=catalog.units(code))


def record_from(attempts: Iterable[s.AttemptIn]) -> StudentRecord:
    return build_record(
        Attempt(
            code=a.code,
            status=a.status,
            term=Term.parse(a.term) if a.term else None,
            grade=a.grade.upper() if a.grade else None,
            units=a.units,
        )
        for a in attempts
    )


def options_from(preferences: s.PreferencesIn, program: Program | None = None) -> PlanOptions:
    """The planner's options from the student's preferences and, when given, the program's standard length."""
    locks = tuple(
        Lock(lock.code, term) for lock in preferences.locks if (term := Term.parse(lock.term)) is not None
    )
    return PlanOptions(
        preferred_units=min(preferences.preferred_units, preferences.max_units),
        max_units=preferences.max_units,
        pace=preferences.pace,
        include_summer=preferences.include_summer,
        summer_max_units=preferences.summer_max_units,
        start_term=Term.parse(preferences.start_term) if preferences.start_term else None,
        locks=locks,
        built_terms=frozenset(term for text in preferences.built_terms if (term := Term.parse(text))),
        exclude=frozenset(preferences.exclude),
        include=frozenset(preferences.include),
        preferences=preferences_from(preferences),
        regular_terms_to_graduate=program.standard_terms
        if program
        else PlanOptions.regular_terms_to_graduate,
    )


def preferences_from(preferences: s.PreferencesIn) -> Preferences:
    return Preferences(
        interests=tuple(preferences.interests),
        goal=preferences.goal,
        workload=preferences.workload,
        plans=preferences.plans,
        avoid=tuple(preferences.avoid),
    )


def program_summary(program: Program) -> s.ProgramSummaryOut:
    return s.ProgramSummaryOut(
        id=program.id,
        name=program.name,
        kind=program.kind,
        catalog_year=program.catalog_year,
        total_units=program.total_units,
        source=program.source,
        source_date=program.source_date,
    )


def group_out(group: Group, catalog: Catalog, include_open_pool: bool = False) -> s.GroupOut:
    courses = [] if group.is_open_pool and not include_open_pool else list(group.courses)
    return s.GroupOut(
        key=group.key,
        title=group.title,
        label=group.label,
        role=group.role.value,
        units_required=group.units_required,
        requires_all=group_requires_all(group, catalog),
        courses=[course_ref(code, catalog) for code in courses],
        children=[group_out(child, catalog) for child in group.children],
    )


def history_out(result: HistoryParseResult) -> s.HistoryParseOut:
    return s.HistoryParseOut(
        rows=[
            s.HistoryRowOut(
                code=row.code,
                title=row.title,
                term=row.term.label if row.term else None,
                grade=row.grade,
                units=row.units,
                status=row.status,
                sis_status=row.sis_status,
                line=row.line,
                issues=row.issues,
            )
            for row in result.rows
        ],
        unread=[s.UnreadLineOut(line=u.line, text=u.text, reason=u.reason) for u in result.unread],
        ignored_line_count=result.ignored_line_count,
        duplicates_removed=result.duplicates_removed,
    )


def _counted(course: CountedCourse, catalog: Catalog, flags: Mapping[str, CourseFlags]) -> s.CountedCourseOut:
    found = flags.get(course.code)
    return s.CountedCourseOut(
        code=course.code,
        title=catalog.title(course.code),
        units=course.units,
        state=course.state.value,
        also_listed=list(found.also_listed) if found else [],
        also_counts_toward=list(found.also_counts_toward) if found else [],
    )


def group_progress_out(
    progress: GroupProgress,
    catalog: Catalog,
    slot_units: dict[str, float],
    flags: Mapping[str, CourseFlags] | None = None,
) -> s.GroupProgressOut:
    flags = flags or {}
    children = [group_progress_out(child, catalog, slot_units, flags) for child in progress.children]
    if progress.children:
        planned = min(
            progress.required - progress.completed - progress.in_progress, sum(c.planned for c in children)
        )
    else:
        planned = progress.planned + slot_units.get(progress.group.key, 0.0)
    planned = max(0.0, planned)
    return s.GroupProgressOut(
        key=progress.group.key,
        label=progress.group.label,
        role=progress.group.role.value,
        units_required=progress.required,
        completed=progress.completed,
        in_progress=progress.in_progress,
        planned=planned,
        remaining=max(0.0, progress.required - progress.completed - progress.in_progress - planned),
        courses=[_counted(c, catalog, flags) for c in progress.courses],
        children=children,
    )


def progress_out(
    progress: ProgramProgress, record: StudentRecord, catalog: Catalog, other: ProgramProgress | None = None
) -> s.ProgressOut:
    """Progress and what is left; ``other`` is the student's other program, for courses counting twice."""
    left = []
    for item in whats_left(progress, catalog):
        left.append(
            s.LeftItemOut(
                group_key=item.group_key,
                group_label=item.group_label,
                units_needed=item.units_needed,
                required_courses=[course_ref(c, catalog) for c in item.required_courses],
                options=[course_ref(c, catalog) for c in item.options],
                open_pool=item.open_pool,
            )
        )
    return s.ProgressOut(
        percent_complete=progress.percent_complete,
        completed_units=record.completed_units(catalog),
        in_progress_units=record.in_progress_units(catalog),
        root=group_progress_out(progress.root, catalog, {}, course_flags(progress, other)),
        not_counted=[course_ref(c.code, catalog) for c in progress.not_counted],
        whats_left=left,
    )


def plan_item_out(
    item: PlanItem, catalog: Catalog, flags: Mapping[str, CourseFlags] | None = None
) -> s.PlanItemOut:
    found = (flags or {}).get(item.code or "")
    return s.PlanItemOut(
        kind=item.kind.value,
        key=item.key,
        code=item.code,
        title=item.title,
        units=item.units,
        reason=item.reason,
        group_key=item.group_key,
        group_label=item.group_label,
        locked=item.locked,
        unlocks=item.unlocks,
        advisories=list(item.advisories),
        suggestions=[course_ref(code, catalog) for code in item.suggestions],
        alternatives=[course_ref(code, catalog) for code in item.alternatives],
        counts_toward=found.counts_toward if found else None,
        also_listed=list(found.also_listed) if found else [],
        also_counts_toward=list(found.also_counts_toward) if found else [],
    )


def eligible_out(course: EligibleCourse, catalog: Catalog) -> s.EligibleOut:
    return s.EligibleOut(
        course=course_ref(course.code, catalog),
        group_key=course.group_key,
        group_label=course.group_label,
        unlocks=course.unlocks,
        advisories=list(course.advisories),
        take_with=list(course.take_with),
    )


def version_out(version: Program, versions: Sequence[Program], in_use: bool = False) -> s.ProgramVersionOut:
    return s.ProgramVersionOut(
        id=version.id,
        name=version.name,
        catalog_year=version.catalog_year,
        valid_from=version.valid_from.label if version.valid_from else None,
        applies_to=version_range(version, versions),
        in_use=in_use,
    )


def family_summary(versions: Sequence[Program]) -> s.ProgramSummaryOut:
    """A program as students choose it: its newest version's details, its id, and every version."""
    newest = versions[-1]
    return program_summary(newest).model_copy(
        update={"id": newest.family_id, "versions": [version_out(v, versions) for v in versions]}
    )


ENTRY_WORDS = {
    "given": "You joined in {entry}",
    "history": "Your first term at AUIB was {entry}",
    "start": "You start in {entry}",
}


def version_note(choice: VersionChoice, entry_source: str) -> str:
    """Which requirements apply to the student, and why, in a sentence (F0.4)."""
    program = choice.program
    whom = version_range(program, choice.versions)
    joined = ENTRY_WORDS[entry_source].format(entry=choice.entry) if choice.entry else "You are starting"
    if choice.how == "chosen":
        return (
            f"You chose the {program.name} requirements for {whom}. Follow a version other than "
            "your own only if the registrar approved it."
        )
    if choice.how == "earliest":
        return (
            f"{joined}, before the earliest {program.name} requirements on file, so the oldest ones "
            f"(for {whom}) are used. Confirm your requirements with the registrar."
        )
    if choice.how == "only":
        return f"These {program.name} requirements apply to {whom}; no other version is on file."
    return f"{joined}, so you follow the {program.name} requirements for {whom}."


def catalog_info(
    program: Program, catalog: Catalog, choice: VersionChoice | None = None, entry_source: str = "start"
) -> s.CatalogInfoOut:
    versions = choice.versions if choice else (program,)
    return s.CatalogInfoOut(
        program_id=program.id,
        program_name=program.name,
        catalog_year=program.catalog_year,
        source=program.source,
        source_date=program.source_date,
        revision=catalog.revision,
        family_id=program.family_id,
        valid_from=program.valid_from.label if program.valid_from else None,
        entry_term=choice.entry.label if choice and choice.entry else None,
        version_choice=choice.how if choice else "only",
        version_note=version_note(choice, entry_source) if choice else "",
        versions=[version_out(v, versions, v.id == program.id) for v in versions],
    )


def degree_map_out(journey: DegreeMap) -> s.DegreeMapOut:
    return s.DegreeMapOut(
        columns=[s.MapColumnOut(label=c.label, kind=c.kind.value) for c in journey.columns],
        nodes=[
            s.MapNodeOut(
                key=n.key,
                code=n.code,
                title=n.title,
                units=n.units,
                status=n.status.value,
                column=n.column,
                group_label=n.group_label,
            )
            for n in journey.nodes
        ],
        edges=[s.MapEdgeOut(source=e.source, target=e.target) for e in journey.edges],
    )


def gpa_out(summary: GpaSummary | None, catalog: Catalog) -> s.GpaOut | None:
    if summary is None:
        return None
    last = summary.last_term
    return s.GpaOut(
        cumulative=summary.cumulative,
        units=summary.units,
        last_term=s.TermGpaOut(term=required_term(last.term), gpa=last.gpa, units=last.units)
        if last
        else None,
        retakes=[
            s.RetakeOut(
                course=course_ref(retake.code, catalog),
                grade=retake.grade,
                with_a=retake.with_a,
                with_b=retake.with_b,
                in_plan=retake.in_plan,
            )
            for retake in summary.retakes
        ],
        assumptions=list(GPA_ASSUMPTIONS),
    )


def building_out(
    planned: PlannedTerm, choices: list[EligibleCourse], plan: Plan, catalog: Catalog
) -> s.BuildingOut:
    terms = plan.course_terms()
    return s.BuildingOut(
        term=required_term(planned.term),
        choices=[
            s.TermChoiceOut(
                **eligible_out(course, catalog).model_dump(),
                planned_for=term_out(terms.get(course.code)),
            )
            for course in choices
        ],
    )


def plan_out(
    plan: Plan,
    program: Program,
    catalog: Catalog,
    record: StudentRecord,
    current: ProgramProgress,
    eligible: list[EligibleCourse],
    in_session: Term,
    minor: Program | None = None,
    minor_current: ProgramProgress | None = None,
    choice: VersionChoice | None = None,
    entry_source: str = "start",
    building: s.BuildingOut | None = None,
) -> s.PlanOut:
    minor_out = None
    if minor is not None and minor_current is not None and plan.minor_progress is not None:
        minor_out = minor_plan_out(minor, minor_current, plan.minor_progress, catalog, current, plan.progress)
    flags = plan_flags(plan)
    return s.PlanOut(
        start_term=required_term(plan.start_term),
        graduation_term=term_out(plan.graduation_term),
        on_time_term=term_out(plan.on_time_term),
        terms=[
            s.PlannedTermOut(
                term=required_term(t.term),
                units=t.units,
                items=[plan_item_out(item, catalog, flags) for item in t.items],
                schedule_published=t.term in catalog.schedules,
                built=t.built,
            )
            for t in plan.terms
        ],
        issues=[s.IssueOut(severity=i.severity, message=i.message, code=i.code) for i in plan.issues],
        unscheduled=[plan_item_out(item, catalog, flags) for item in plan.unscheduled],
        critical_chain=[course_ref(code, catalog) for code in plan.critical_chain],
        progress=progress_out(current, record, catalog, minor_current),
        progress_with_plan=group_progress_out(plan.progress.root, catalog, plan.slot_units, flags),
        eligible_next_term=[eligible_out(course, catalog) for course in eligible],
        building=building,
        degree_map=degree_map_out(degree_map(plan, record, catalog, program, in_session)),
        gpa=gpa_out(gpa_summary(record, catalog, set(plan.course_terms())), catalog),
        minor=minor_out,
        catalog=catalog_info(program, catalog, choice, entry_source),
        assumptions=plan_assumptions(catalog),
        disclaimer=DISCLAIMER,
    )


def plan_flags(plan: Plan) -> dict[str, CourseFlags]:
    """Where each planned course counts (F1.7): toward the major, or else toward the minor."""
    flags = course_flags(plan.progress, plan.minor_progress)
    if plan.minor_progress is not None:
        minor = plan.minor_progress.program
        for code, found in course_flags(plan.minor_progress).items():
            if code not in flags and found.counts_toward:
                flags[code] = replace(found, counts_toward=with_program(found.counts_toward, minor))
    return flags


def minor_plan_out(
    minor: Program,
    current: ProgramProgress,
    with_plan: ProgramProgress,
    catalog: Catalog,
    major_current: ProgramProgress | None = None,
    major_with_plan: ProgramProgress | None = None,
) -> s.MinorPlanOut:
    """The minor's own progress: units count only where they count toward the minor."""
    left = [
        s.LeftItemOut(
            group_key=item.group_key,
            group_label=item.group_label,
            units_needed=item.units_needed,
            required_courses=[course_ref(c, catalog) for c in item.required_courses],
            options=[course_ref(c, catalog) for c in item.options],
            open_pool=item.open_pool,
        )
        for item in whats_left(current, catalog)
    ]
    return s.MinorPlanOut(
        program_id=minor.id,
        name=minor.name,
        total_units=minor.total_units,
        source=minor.source,
        source_date=minor.source_date,
        valid_from=minor.valid_from.label if minor.valid_from else None,
        progress=s.ProgressOut(
            percent_complete=current.percent_complete,
            completed_units=current.root.completed,
            in_progress_units=current.root.in_progress,
            root=group_progress_out(current.root, catalog, {}, course_flags(current, major_current)),
            not_counted=[],  # most courses do not count toward a minor; that is not worth listing
            whats_left=left,
        ),
        progress_with_plan=group_progress_out(
            with_plan.root, catalog, {}, course_flags(with_plan, major_with_plan)
        ),
    )


def suggestions_out(found: GroupSuggestions, catalog: Catalog) -> s.GroupSuggestionsOut:
    return s.GroupSuggestionsOut(
        group_key=found.group.key,
        group_label=found.group.label,
        units_needed=found.units_needed,
        suggestions=[
            s.SuggestionOut(
                course=course_ref(suggestion.code, catalog),
                score=suggestion.score,
                reasons=list(suggestion.reasons),
                eligible_now=suggestion.eligible_now,
                missing=list(suggestion.missing),
            )
            for suggestion in found.suggestions
        ],
    )


def standing_credits() -> dict[str, int]:
    return {standing.value: credits for standing, credits in DEFAULT_STANDING_CREDITS.items()}


def shift_out(shift: Shift) -> s.ShiftOut:
    return s.ShiftOut(
        code=shift.code, title=shift.title, before=term_out(shift.before), after=term_out(shift.after)
    )


def move_choices_out(choices: MoveChoices, code: str, catalog: Catalog) -> s.MoveOptionsOut:
    return s.MoveOptionsOut(
        course=course_ref(code, catalog),
        term=required_term(choices.source),
        graduation_term=term_out(choices.plan.graduation_term),
        options=[
            s.MoveOptionOut(
                term=required_term(move.term),
                valid=move.valid,
                problems=list(move.problems),
                graduation_term=term_out(move.graduation_term),
                terms_later=move.terms_later,
                shifts=[shift_out(shift) for shift in move.shifts],
            )
            for move in choices.moves
        ],
    )


def scenario_plan_out(
    plan: Plan,
    program: Program,
    minor: Program | None,
    current: ProgramProgress,
    catalog: Catalog,
    semesters_vs_first: int | None,
) -> s.ScenarioPlanOut:
    """A saved plan in brief, for comparing side by side (F6.2)."""
    return s.ScenarioPlanOut(
        program_name=program.name,
        minor_name=minor.name if minor else None,
        catalog_year=program.catalog_year,
        graduation_term=term_out(plan.graduation_term),
        on_time_term=term_out(plan.on_time_term),
        semesters_vs_first=semesters_vs_first,
        percent_complete=current.percent_complete,
        counted_credits=counted_units(current),
        credits_left=units_left(current),
        planned_credits=sum(t.units for t in plan.terms),
        warnings=sum(1 for issue in plan.issues if issue.severity == "warning"),
        terms=[
            s.ScenarioTermOut(
                term=required_term(t.term),
                units=t.units,
                built=t.built,
                courses=[course_ref(item.code, catalog) for item in t.items if item.code],
                open_choices=[item.group_label or item.title for item in t.items if item.code is None],
            )
            for t in plan.terms
        ],
    )


def program_side_out(
    program: Program, minor: Program | None, progress: ProgramProgress, plan: Plan
) -> s.ProgramSideOut:
    return s.ProgramSideOut(
        program_id=program.family_id,
        name=program.name,
        minor_name=minor.name if minor else None,
        catalog_year=program.catalog_year,
        total_credits=progress.root.required,
        counted_credits=counted_units(progress),
        credits_left=units_left(progress),
        percent_complete=progress.percent_complete,
        graduation_term=term_out(plan.graduation_term),
        on_time_term=term_out(plan.on_time_term),
    )


CHANGE_NOTES = [
    "Your completed and in-progress courses are counted toward the new major the same way as toward your "
    "own: each counts toward the first requirement, in SIS order, that still needs it.",
    "The new plan starts fresh: the courses you placed and the terms you built stay with your current plan. "
    "Your credit load, pace, summer and interest settings carry over.",
    "The registrar decides which requirements apply after a change of major and how your courses count. "
    "Talk to your advisor before you apply.",
]


def program_change_out(
    change: ProgramChange,
    current: Program,
    current_minor: Program | None,
    target: Program,
    target_minor: Program | None,
    catalog: Catalog,
    version: str,
) -> s.ProgramChangeOut:
    """What changing major or minor would do (F6.3)."""
    return s.ProgramChangeOut(
        current=program_side_out(current, current_minor, change.current, change.current_plan),
        target=program_side_out(target, target_minor, change.target, change.target_plan),
        terms_later=change.terms_later,
        courses=[
            s.TransferCourseOut(
                course=course_ref(course.code, catalog),
                state="completed" if course.state is CourseState.COMPLETED else "in_progress",
                now=course.now,
                after=course.after,
                after_minor=course.after_minor,
            )
            for course in change.courses
        ],
        lost_credits=sum(course.units for course in change.lost),
        version_note=version,
        notes=CHANGE_NOTES,
    )
