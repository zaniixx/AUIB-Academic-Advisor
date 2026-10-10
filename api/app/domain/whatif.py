"""What happens if I drop, delay or move a course (F1.5, F6.1).

Dropping an in-progress course (failing or withdrawing this term) means it has
to be taken again; delaying a planned course pushes it at least one term later.
Both re-plan with everything else unchanged and report the new graduation term
and every course that moves.

Moving a planned course to a term the student picks (dragging it there, F6.1)
re-plans with the course placed in that term, then checks the result: the
course must run then, have its prerequisites done in earlier terms and its
corequisites by that term, keep the term within the credit limit, and leave
every course the student placed with what it needs. A move that breaks one of
these is explained, not just refused.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from app.domain.catalog import Catalog, Program, level_courses
from app.domain.planner import Lock, Plan, PlanOptions, build_plan
from app.domain.progress import EPSILON
from app.domain.record import Attempt, AttemptStatus, StudentRecord, build_record
from app.domain.requisites import EvalContext, evaluate
from app.domain.terms import Season, Term, terms_between

MAX_MOVE_TERMS = 16  # terms checked for one move; a plan rarely has more


class ChangeAction(StrEnum):
    DROP = "drop"  # an in-progress course is failed or withdrawn this term
    DELAY = "delay"  # a planned course moves at least one term later


@dataclass(frozen=True)
class Change:
    code: str
    action: ChangeAction


@dataclass(frozen=True)
class Shift:
    code: str
    title: str
    before: Term | None  # None: was not in the plan
    after: Term | None  # None: no longer in the plan (or could not be scheduled)


@dataclass(frozen=True)
class WhatIf:
    before: Plan
    after: Plan
    shifts: tuple[Shift, ...]
    terms_later: int  # how many terms later graduation moves (negative if earlier)


class WhatIfError(ValueError):
    pass


def what_if(
    program: Program,
    catalog: Catalog,
    record: StudentRecord,
    options: PlanOptions,
    change: Change,
    today: date,
    minor: Program | None = None,
) -> WhatIf:
    before = build_plan(program, catalog, record, options, today, minor)
    new_record, new_options = record, options

    if change.code in record.in_progress:
        new_record = build_record(
            replace(attempt, status=AttemptStatus.WITHDRAWN)
            if attempt.code == change.code and attempt.status is AttemptStatus.IN_PROGRESS
            else attempt
            for attempt in record.attempts
        )
    elif (planned_term := before.term_of(change.code)) is not None:
        later = planned_term.next(options.include_summer)
        new_options = replace(
            options,
            locks=tuple(lock for lock in options.locks if lock.code != change.code),
            not_before=(*options.not_before, (change.code, later)),
        )
    else:
        raise WhatIfError(f"{change.code} is not in progress or in your plan")

    after = build_plan(program, catalog, new_record, new_options, today, minor)
    before_terms = before.course_terms()
    if change.code in record.in_progress:
        before_terms.setdefault(change.code, _attempt_term(record.attempts, change.code) or before.start_term)
    return WhatIf(
        before,
        after,
        _shifts(before_terms, after.course_terms(), catalog),
        terms_between(before.graduation_term, after.graduation_term, options.include_summer),
    )


def _attempt_term(attempts: tuple[Attempt, ...], code: str) -> Term | None:
    return next((a.term for a in attempts if a.code == code and a.term), None)


def _shifts(before: Mapping[str, Term], after: Mapping[str, Term], catalog: Catalog) -> tuple[Shift, ...]:
    """Every course whose term differs between two plans."""
    return tuple(
        Shift(code, catalog.title(code), before.get(code), after.get(code))
        for code in sorted(before.keys() | after.keys())
        if before.get(code) != after.get(code)
    )


# ---------------------------------------------------------------------------
# Moving a course to another term (F6.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Move:
    """A planned course put in another term: whether it can go there, and what that changes."""

    code: str
    term: Term
    problems: tuple[str, ...]  # why it cannot go there, in plain words; empty when it can
    graduation_term: Term | None  # with the course there; None when the move was not planned
    terms_later: int
    shifts: tuple[Shift, ...]

    @property
    def valid(self) -> bool:
        return not self.problems


def moved_options(options: PlanOptions, code: str, source: Term | None, target: Term) -> PlanOptions:
    """``options`` with ``code`` placed in ``target``, as the web app saves a move.

    A term the student built that loses its last course is open again, as when the student
    removes that course from it.
    """
    locks = (*(lock for lock in options.locks if lock.code != code), Lock(code, target))
    built = options.built_terms
    if source is not None and source in built and not any(lock.term == source for lock in locks):
        built = built - {source}
    return replace(
        options,
        locks=locks,
        built_terms=built,
        not_before=tuple(item for item in options.not_before if item[0] != code),
        exclude=options.exclude - {code},
    )


@dataclass(frozen=True)
class MoveChoices:
    """A planned course and every term it could be moved to, each checked."""

    plan: Plan  # the plan as it is
    source: Term  # the term the plan has the course in
    moves: tuple[Move, ...]


def move_options(
    program: Program,
    catalog: Catalog,
    record: StudentRecord,
    options: PlanOptions,
    code: str,
    today: date,
    minor: Program | None = None,
) -> MoveChoices:
    """``code`` checked in every other term of the plan and in the term after its last."""
    if code in record.have:
        raise WhatIfError(f"{code} is already completed or in progress")
    before = build_plan(program, catalog, record, options, today, minor, alternatives=False)
    source = before.term_of(code)
    if source is None:
        raise WhatIfError(f"{code} is not in your plan")
    targets = [planned.term for planned in before.terms if planned.term != source]
    # The term after the plan's last, so a course can also go to the very end.
    targets.append(before.terms[-1].term.next())
    moves = tuple(
        move_course(program, catalog, record, options, code, target, today, minor, before)
        for target in targets[:MAX_MOVE_TERMS]
    )
    return MoveChoices(before, source, moves)


def move_course(
    program: Program,
    catalog: Catalog,
    record: StudentRecord,
    options: PlanOptions,
    code: str,
    term: Term,
    today: date,
    minor: Program | None = None,
    before: Plan | None = None,
) -> Move:
    """Re-plan with ``code`` in ``term`` and say whether the result holds (F6.1)."""
    if before is None:
        before = build_plan(program, catalog, record, options, today, minor, alternatives=False)
    source = before.term_of(code)
    if source is None:
        raise WhatIfError(f"{code} is not in your plan")
    if term < before.start_term:
        problem = f"{term.label} has started or passed; your plan starts in {before.start_term.label}."
        return Move(code, term, (problem,), None, 0, ())
    if not catalog.offered(code, term):
        return Move(code, term, (_not_offered(catalog, code, term),), None, 0, ())

    new_options = moved_options(options, code, source, term)
    after = build_plan(program, catalog, record, new_options, today, minor, alternatives=False)
    level_map = level_courses(program, catalog)
    problems: list[str] = []
    if after.term_of(code) != term:
        problems.append(f"{code} could not be planned in {term.label}.")
    else:
        needs_first, needs_with = _unmet(after, code, record, catalog, new_options, level_map)
        if needs_first:
            problems.append(f"{code} needs {_join(needs_first)} done before {term.label}.")
        if needs_with:
            problems.append(f"{code} needs {_join(needs_with)} in {term.label} or earlier.")
        load = next(planned.units for planned in after.terms if planned.term == term)
        limit = options.summer_max_units if term.season is Season.SUMMER else options.max_units
        if load > limit + EPSILON:
            problems.append(
                f"{term.label} would have {load:g} credits, over your limit of {limit:g}. "
                "Raise the limit in Adjust plan to allow it."
            )
    # Courses the student placed themselves stay where they are, so a move must not take away
    # something one of them needs.
    for lock in new_options.locks:
        if lock.code == code or after.term_of(lock.code) is None:
            continue
        first, together = _unmet(after, lock.code, record, catalog, new_options, level_map)
        if (first or together) and not any(_unmet(before, lock.code, record, catalog, options, level_map)):
            missing = _join([*first, *together])
            problems.append(
                f"You placed {lock.code} in {lock.term.label}; it would no longer have {missing}."
            )
    return Move(
        code,
        term,
        tuple(problems),
        after.graduation_term,
        terms_between(before.graduation_term, after.graduation_term, options.include_summer),
        _shifts(before.course_terms(), after.course_terms(), catalog),
    )


def _unmet(
    plan: Plan,
    code: str,
    record: StudentRecord,
    catalog: Catalog,
    options: PlanOptions,
    level_map: Mapping[int, frozenset[str]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What ``code`` lacks where ``plan`` has it: prerequisites not done in earlier terms, and
    corequisites neither done nor taken in the same term."""
    term = plan.term_of(code)
    if term is None:
        return (), ()
    earlier = [planned for planned in plan.terms if planned.term < term]
    same = next(planned for planned in plan.terms if planned.term == term)
    context = EvalContext(
        completed=record.have | {item.code for planned in earlier for item in planned.items if item.code},
        credits=record.completed_units(catalog)
        + record.in_progress_units(catalog)
        + sum(planned.units for planned in earlier),
        level_courses=level_map,
        standing_credits=options.standing_credits,
    )
    alongside = replace(
        context, concurrent=frozenset(item.code for item in same.items if item.code and item.code != code)
    )
    first = evaluate(catalog.prerequisite(code), context).missing
    together = tuple(
        missing for rule in catalog.corequisites(code) for missing in evaluate(rule, alongside).missing
    )
    return first, together


def _not_offered(catalog: Catalog, code: str, term: Term) -> str:
    course = catalog.courses.get(code)
    if course is None or course.hidden:
        return f"{code} is not offered at the moment."
    if not course.offered_in(term.season):
        seasons = " and ".join(season.label for season in sorted(course.offered_terms or ()))
        return f"{code} runs in {seasons} only, not in {term.season.label}."
    return f"{code} is not on the published {term.label} course schedule."


def _join(items: list[str] | tuple[str, ...]) -> str:
    items = list(dict.fromkeys(items))
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
