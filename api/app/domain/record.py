"""A student's course attempts and what they add up to.

Grade handling follows common US practice until AUIB confirms its own rules
(listed in the requirements document's open questions): any grade from A+ to
D- passes, and only completed or in-progress courses count toward a degree.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.domain.catalog import Catalog
from app.domain.terms import Term


class AttemptStatus(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    WITHDRAWN = "withdrawn"
    INCOMPLETE = "incomplete"
    NOT_COUNTED = "not_counted"  # audited, or an attempt SIS marks as repeated


GRADE_POINTS: dict[str, float] = {
    "A+": 4.0, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0, "D-": 0.7,
    "F": 0.0,
}  # fmt: skip
PASSING_NON_LETTER = {"P", "CR", "TR", "S"}
FAILING = {"F", "NP", "WF", "U", "FA"}
WITHDRAWN = {"W", "WP", "DR"}
ALL_GRADES = set(GRADE_POINTS) | PASSING_NON_LETTER | FAILING | WITHDRAWN | {"I", "IP", "AU"}


def status_from_grade(grade: str | None) -> AttemptStatus | None:
    """Status implied by a grade alone, or None when the grade says nothing."""
    if not grade:
        return None
    grade = grade.upper()
    if (grade in GRADE_POINTS and grade not in FAILING) or grade in PASSING_NON_LETTER:
        return AttemptStatus.COMPLETED
    if grade in FAILING:
        return AttemptStatus.FAILED
    if grade in WITHDRAWN:
        return AttemptStatus.WITHDRAWN
    if grade == "I":
        return AttemptStatus.INCOMPLETE
    if grade == "IP":
        return AttemptStatus.IN_PROGRESS
    if grade == "AU":
        return AttemptStatus.NOT_COUNTED
    return None


@dataclass(frozen=True)
class Attempt:
    code: str
    status: AttemptStatus
    term: Term | None = None
    grade: str | None = None
    units: float | None = None


@dataclass(frozen=True)
class StudentRecord:
    attempts: tuple[Attempt, ...]
    completed: frozenset[str]
    in_progress: frozenset[str]
    unit_overrides: dict[str, float]  # units from the history where SIS shows them (transfer credit)

    @property
    def have(self) -> frozenset[str]:
        """Courses done or under way; the planner assumes in-progress courses will pass."""
        return self.completed | self.in_progress

    def units_of(self, code: str, catalog: Catalog) -> float:
        return self.unit_overrides.get(code, catalog.units(code))

    def completed_units(self, catalog: Catalog) -> float:
        return sum(self.units_of(code, catalog) for code in self.completed)

    def in_progress_units(self, catalog: Catalog) -> float:
        return sum(self.units_of(code, catalog) for code in self.in_progress)

    def failed_or_withdrawn(self) -> frozenset[str]:
        tried = {a.code for a in self.attempts if a.status in (AttemptStatus.FAILED, AttemptStatus.WITHDRAWN)}
        return frozenset(tried - self.have)

    def first_term(self) -> Term | None:
        terms = [a.term for a in self.attempts if a.term is not None]
        return min(terms) if terms else None


def build_record(attempts: Iterable[Attempt]) -> StudentRecord:
    attempts = tuple(attempts)
    completed = {a.code for a in attempts if a.status is AttemptStatus.COMPLETED}
    in_progress = {a.code for a in attempts if a.status is AttemptStatus.IN_PROGRESS} - completed
    overrides: dict[str, float] = {}
    for attempt in attempts:
        if attempt.units and attempt.status in (AttemptStatus.COMPLETED, AttemptStatus.IN_PROGRESS):
            overrides[attempt.code] = attempt.units
    return StudentRecord(attempts, frozenset(completed), frozenset(in_progress), overrides)
