"""What happens if I drop or delay a course (F1.5).

Dropping an in-progress course (failing or withdrawing this term) means it has
to be taken again; delaying a planned course pushes it at least one term later.
Both re-plan with everything else unchanged and report the new graduation term
and every course that moves.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from app.domain.catalog import Catalog, Program
from app.domain.planner import Plan, PlanOptions, build_plan
from app.domain.record import Attempt, AttemptStatus, StudentRecord, build_record
from app.domain.terms import Term


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
    before_terms, after_terms = before.course_terms(), after.course_terms()
    if change.code in record.in_progress:
        before_terms.setdefault(change.code, _attempt_term(record.attempts, change.code) or before.start_term)
    shifts = tuple(
        Shift(code, catalog.title(code), before_terms.get(code), after_terms.get(code))
        for code in sorted(before_terms.keys() | after_terms.keys())
        if before_terms.get(code) != after_terms.get(code)
    )
    return WhatIf(
        before,
        after,
        shifts,
        _terms_between(before.graduation_term, after.graduation_term, options.include_summer),
    )


def _attempt_term(attempts: tuple[Attempt, ...], code: str) -> Term | None:
    return next((a.term for a in attempts if a.code == code and a.term), None)


def _terms_between(first: Term | None, second: Term | None, include_summer: bool) -> int:
    if first is None or second is None or first == second:
        return 0
    sign = 1 if second > first else -1
    low, high = (first, second) if sign > 0 else (second, first)
    count = 0
    while low < high:
        low = low.next(include_summer)
        count += 1
    return sign * count
