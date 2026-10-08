"""Cumulative and term GPA, and which retakes would raise the CGPA most (F7.1, F7.3).

AUIB has not yet confirmed its grading rules (requirements document, open questions),
so this follows common US practice and says so wherever a GPA is shown:

* grade points on the 4.0 scale in ``record.GRADE_POINTS`` (A+ and A are 4.0);
* WF counts as F; P, CR, TR, W, I and AU carry no grade points;
* when a course is retaken, the latest graded attempt replaces earlier ones in the
  CGPA (attempts SIS marks "Repeated" are already excluded);
* a term GPA counts every graded attempt in that term.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from app.domain.catalog import Catalog
from app.domain.record import GRADE_POINTS, Attempt, AttemptStatus, StudentRecord
from app.domain.terms import Season, Term

RETAKE_BELOW = 3.0  # suggest retaking courses graded below B
RETAKE_SUGGESTIONS = 3
EARLIEST = Term(1, Season.SPRING)
GPA_ASSUMPTIONS = (
    "GPA uses the 4.0 scale (A+ and A are 4.0, A- 3.7, B+ 3.3 down to F 0); WF counts as F.",
    "A retaken course's newest grade replaces the old one in your CGPA.",
    "AUIB has not confirmed these rules yet; the GPA in SIS is the official one.",
)


@dataclass(frozen=True)
class TermGpa:
    term: Term
    gpa: float
    units: float


@dataclass(frozen=True)
class Retake:
    code: str
    grade: str
    units: float
    with_a: float  # CGPA if the retake earns an A
    with_b: float  # CGPA if the retake earns a B
    in_plan: bool  # already planned (a failed course that must be retaken anyway)


@dataclass(frozen=True)
class GpaSummary:
    cumulative: float
    units: float
    quality_points: float
    last_term: TermGpa | None
    retakes: tuple[Retake, ...]


def grade_points(attempt: Attempt) -> float | None:
    """Points per unit for a graded attempt, or None when the attempt carries no GPA grade."""
    if attempt.status in (AttemptStatus.IN_PROGRESS, AttemptStatus.NOT_COUNTED) or not attempt.grade:
        return None
    grade = attempt.grade.upper()
    if grade == "WF":
        return 0.0
    return GRADE_POINTS.get(grade)


def gpa_summary(record: StudentRecord, catalog: Catalog, in_plan: Collection[str] = ()) -> GpaSummary | None:
    graded = [(a, p) for a in record.attempts if (p := grade_points(a)) is not None]
    if not graded:
        return None

    def units(attempt: Attempt) -> float:
        return attempt.units if attempt.units else catalog.units(attempt.code)

    # Latest graded attempt per course; attempts without a term sort as the earliest.
    latest: dict[str, tuple[Attempt, float]] = {}
    ordered = sorted(enumerate(graded), key=lambda pair: (pair[1][0].term or EARLIEST, pair[0]))
    for _index, (attempt, points) in ordered:
        latest[attempt.code] = (attempt, points)

    total_units = sum(units(a) for a, _ in latest.values())
    quality = sum(units(a) * p for a, p in latest.values())
    if total_units <= 0:
        return None
    cumulative = quality / total_units

    terms = [a.term for a, _ in graded if a.term is not None]
    last_term = None
    if terms:
        last = max(terms)
        in_term = [(a, p) for a, p in graded if a.term == last]
        term_units = sum(units(a) for a, _ in in_term)
        if term_units > 0:
            last_term = TermGpa(
                last, round(sum(units(a) * p for a, p in in_term) / term_units, 2), term_units
            )

    retakes = []
    for code, (attempt, points) in latest.items():
        course = catalog.courses.get(code)
        if points >= RETAKE_BELOW or course is None or course.is_placeholder:
            continue
        size = units(attempt)

        def projected(new_points: float, size: float = size, points: float = points) -> float:
            return round((quality - size * points + size * new_points) / total_units, 2)

        retakes.append(
            Retake(
                code=code,
                grade=(attempt.grade or "").upper(),
                units=size,
                with_a=projected(GRADE_POINTS["A"]),
                with_b=projected(GRADE_POINTS["B"]),
                in_plan=code in in_plan,
            )
        )
    retakes.sort(key=lambda r: (-(r.with_a - cumulative), r.code))
    return GpaSummary(
        cumulative=round(cumulative, 2),
        units=total_units,
        quality_points=round(quality, 2),
        last_term=last_term,
        retakes=tuple(retakes[:RETAKE_SUGGESTIONS]),
    )
