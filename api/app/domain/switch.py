"""What changing major or minor would do (F6.3).

The student's completed and in-progress courses are counted against the new
major (and minor) exactly as against their own (``allocate``), so the report
shows, course by course, where each counts now and where it would count after
the change, and how many credits carry over. Both programs are then planned to
graduation. The new program's plan starts fresh: courses the student placed,
terms they built and courses they chose or ruled out belong to their current
plan, so only their load, pace, summer and interest settings carry over.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from app.domain.catalog import Catalog, Program
from app.domain.planner import Plan, PlanOptions, build_plan, current_progress
from app.domain.progress import EPSILON, CourseState, ProgramProgress
from app.domain.record import StudentRecord
from app.domain.terms import terms_between


@dataclass(frozen=True)
class TransferredCourse:
    """One completed or in-progress course and the requirement it counts toward before and after."""

    code: str
    units: float
    state: CourseState
    now: str | None  # requirement in the current major (or minor); None when it counts toward neither
    after: str | None  # requirement in the new major; None when it does not count
    after_minor: str | None  # requirement in the new minor, when there is one


@dataclass(frozen=True)
class ProgramChange:
    current: ProgramProgress
    target: ProgramProgress
    target_minor: ProgramProgress | None
    current_plan: Plan
    target_plan: Plan
    courses: tuple[TransferredCourse, ...]
    terms_later: int  # how many terms later the new program finishes (negative if earlier)

    @property
    def lost(self) -> tuple[TransferredCourse, ...]:
        """Courses that count toward the current program but not the new major or minor."""
        return tuple(c for c in self.courses if c.now and not c.after and not c.after_minor)


def fresh_options(options: PlanOptions, program: Program) -> PlanOptions:
    """``options`` for planning ``program`` from scratch: the student's settings, not their placements."""
    return replace(
        options,
        locks=(),
        built_terms=frozenset(),
        include=frozenset(),
        exclude=frozenset(),
        not_before=(),
        regular_terms_to_graduate=program.standard_terms,
    )


def change_program(
    current: Program,
    target: Program,
    catalog: Catalog,
    record: StudentRecord,
    options: PlanOptions,
    today: date,
    current_minor: Program | None = None,
    target_minor: Program | None = None,
) -> ProgramChange:
    now = current_progress(current, catalog, record)
    now_minor = current_progress(current_minor, catalog, record) if current_minor else None
    after = current_progress(target, catalog, record)
    after_minor = current_progress(target_minor, catalog, record) if target_minor else None
    current_plan = build_plan(current, catalog, record, options, today, current_minor, alternatives=False)
    target_plan = build_plan(
        target, catalog, record, fresh_options(options, target), today, target_minor, alternatives=False
    )

    def where(progress: ProgramProgress | None, code: str) -> str | None:
        leaf = progress.leaf_for(code) if progress is not None else None
        return leaf.group.label if leaf is not None else None

    taken = [(code, CourseState.COMPLETED) for code in sorted(record.completed)]
    taken += [(code, CourseState.IN_PROGRESS) for code in sorted(record.in_progress)]
    courses = tuple(
        TransferredCourse(
            code=code,
            units=record.units_of(code, catalog),
            state=state,
            now=where(now, code) or where(now_minor, code),
            after=where(after, code),
            after_minor=where(after_minor, code),
        )
        for code, state in taken
    )
    return ProgramChange(
        current=now,
        target=after,
        target_minor=after_minor,
        current_plan=current_plan,
        target_plan=target_plan,
        courses=courses,
        terms_later=terms_between(
            current_plan.graduation_term, target_plan.graduation_term, options.include_summer
        ),
    )


def counted_units(progress: ProgramProgress) -> float:
    """Completed and in-progress credits that count toward ``progress``'s program."""
    return progress.root.completed + progress.root.in_progress


def units_left(progress: ProgramProgress) -> float:
    left = progress.root.remaining_after_current
    return 0.0 if left <= EPSILON else left
