"""Turn requests into domain objects and domain results into responses."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.api import schemas as s
from app.domain.catalog import Catalog, Group, Program, VersionChoice, group_requires_all, version_range
from app.domain.gpa import GPA_ASSUMPTIONS, GpaSummary, gpa_summary
from app.domain.history import HistoryParseResult
from app.domain.journey import DegreeMap, degree_map
from app.domain.planner import EligibleCourse, Lock, Plan, PlanItem, PlanOptions
from app.domain.progress import CountedCourse, GroupProgress, ProgramProgress, whats_left
from app.domain.recommend import GroupSuggestions, Preferences
from app.domain.record import Attempt, StudentRecord, build_record
from app.domain.requisites import DEFAULT_STANDING_CREDITS
from app.domain.terms import Term
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


def options_from(preferences: s.PreferencesIn) -> PlanOptions:
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
        exclude=frozenset(preferences.exclude),
        include=frozenset(preferences.include),
        preferences=preferences_from(preferences),
    )


def preferences_from(preferences: s.PreferencesIn) -> Preferences:
    return Preferences(
        interests=tuple(preferences.interests), goal=preferences.goal, workload=preferences.workload
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


def _counted(course: CountedCourse, catalog: Catalog) -> s.CountedCourseOut:
    return s.CountedCourseOut(
        code=course.code,
        title=catalog.title(course.code),
        units=course.units,
        state=course.state.value,
    )


def group_progress_out(
    progress: GroupProgress, catalog: Catalog, slot_units: dict[str, float]
) -> s.GroupProgressOut:
    children = [group_progress_out(child, catalog, slot_units) for child in progress.children]
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
        courses=[_counted(c, catalog) for c in progress.courses],
        children=children,
    )


def progress_out(progress: ProgramProgress, record: StudentRecord, catalog: Catalog) -> s.ProgressOut:
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
        root=group_progress_out(progress.root, catalog, {}),
        not_counted=[course_ref(c.code, catalog) for c in progress.not_counted],
        whats_left=left,
    )


def plan_item_out(item: PlanItem, catalog: Catalog) -> s.PlanItemOut:
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
) -> s.PlanOut:
    minor_out = None
    if minor is not None and minor_current is not None and plan.minor_progress is not None:
        minor_out = minor_plan_out(minor, minor_current, plan.minor_progress, catalog)
    return s.PlanOut(
        start_term=required_term(plan.start_term),
        graduation_term=term_out(plan.graduation_term),
        on_time_term=term_out(plan.on_time_term),
        terms=[
            s.PlannedTermOut(
                term=required_term(t.term),
                units=t.units,
                items=[plan_item_out(item, catalog) for item in t.items],
                schedule_published=t.term in catalog.schedules,
            )
            for t in plan.terms
        ],
        issues=[s.IssueOut(severity=i.severity, message=i.message, code=i.code) for i in plan.issues],
        unscheduled=[plan_item_out(item, catalog) for item in plan.unscheduled],
        critical_chain=[course_ref(code, catalog) for code in plan.critical_chain],
        progress=progress_out(current, record, catalog),
        progress_with_plan=group_progress_out(plan.progress.root, catalog, plan.slot_units),
        eligible_next_term=[eligible_out(course, catalog) for course in eligible],
        degree_map=degree_map_out(degree_map(plan, record, catalog, program, in_session)),
        gpa=gpa_out(gpa_summary(record, catalog, set(plan.course_terms())), catalog),
        minor=minor_out,
        catalog=catalog_info(program, catalog, choice, entry_source),
        assumptions=plan_assumptions(catalog),
        disclaimer=DISCLAIMER,
    )


def minor_plan_out(
    minor: Program, current: ProgramProgress, with_plan: ProgramProgress, catalog: Catalog
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
            root=group_progress_out(current.root, catalog, {}),
            not_counted=[],  # most courses do not count toward a minor; that is not worth listing
            whats_left=left,
        ),
        progress_with_plan=group_progress_out(with_plan.root, catalog, {}),
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
