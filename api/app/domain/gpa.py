"""Cumulative and term GPA, retakes that raise the CGPA most, projections and targets (F7.1–F7.3).

AUIB has not yet confirmed its grading rules (requirements document, open questions),
so this follows common US practice and says so wherever a GPA is shown:

* grade points on the 4.0 scale in ``record.GRADE_POINTS`` (A+ and A are 4.0);
* WF counts as F; P, CR, TR, W, I and AU carry no grade points;
* when a course is retaken, the latest graded attempt replaces earlier ones in the
  CGPA (attempts SIS marks "Repeated" are already excluded);
* a term GPA counts every graded attempt in that term.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

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


# ---------------------------------------------------------------------------
# Projection (F7.2) and the grades needed for a target (F7.3)
# ---------------------------------------------------------------------------

TargetStatus = Literal["met", "reachable", "out_of_reach", "no_courses"]

# Letter grades a student can expect, lowest first (A+ counts the same as A, so it is left out).
GRADE_CHOICES = ("F", "D-", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A")


@dataclass(frozen=True)
class GradeProjection:
    cumulative: float | None  # the CGPA once the expected grades are in
    courses_gpa: float | None  # the GPA of the courses with an expected grade, on their own
    units: float  # graded units counted in that CGPA


@dataclass(frozen=True)
class TargetPlan:
    """What the courses without an expected grade need to average for the CGPA to reach ``target``."""

    target: float
    open_units: float
    status: TargetStatus  # "met": even F's keep the CGPA at the target
    average_needed: float | None  # grade points per unit, rounded up
    grade_needed: str | None  # the lowest letter grade at or above that average
    best_possible: float | None  # the CGPA with an A in every open course


def project_gpa(record: StudentRecord, catalog: Catalog, expected: Mapping[str, str]) -> GradeProjection:
    """The CGPA if each course in ``expected`` (code -> letter grade) earns that grade.

    An expected grade is the newest attempt, so it replaces an earlier grade in the same course.
    """
    extra = {code: GRADE_POINTS[grade] for code, grade in expected.items()}
    latest = _latest_graded(record, catalog, extra)
    units = sum(size for size, _ in latest.values())
    sizes = {code: record.units_of(code, catalog) for code in extra}
    course_units = sum(sizes.values())
    courses_gpa = sum(sizes[c] * p for c, p in extra.items()) / course_units if course_units > 0 else None
    return GradeProjection(
        cumulative=_rounded(_cgpa(latest)),
        courses_gpa=_rounded(courses_gpa),
        units=units,
    )


def grades_for_target(
    record: StudentRecord,
    catalog: Catalog,
    expected: Mapping[str, str],
    open_codes: Sequence[str],
    target: float,
) -> TargetPlan:
    """The average grade the ``open_codes`` courses need, with ``expected`` grades for the rest."""
    fixed = {code: GRADE_POINTS[grade] for code, grade in expected.items()}
    courses = [code for code in dict.fromkeys(open_codes) if code not in fixed]
    open_units = sum(record.units_of(code, catalog) for code in courses)
    if not courses or open_units <= 0:
        return TargetPlan(target, 0.0, "no_courses", None, None, None)

    def cgpa_at(points: float) -> float:
        value = _cgpa(_latest_graded(record, catalog, {**fixed, **dict.fromkeys(courses, points)}))
        return value if value is not None else 0.0

    best = cgpa_at(GRADE_POINTS["A"])
    if cgpa_at(GRADE_POINTS["F"]) >= target - 1e-9:
        return TargetPlan(target, open_units, "met", 0.0, "F", _rounded(best))
    if best < target - 1e-9:
        return TargetPlan(target, open_units, "out_of_reach", None, None, _rounded(best))
    low, high = GRADE_POINTS["F"], GRADE_POINTS["A"]
    for _ in range(40):  # the CGPA grows with the average, so halve the range until it is exact
        middle = (low + high) / 2
        if cgpa_at(middle) >= target - 1e-9:
            high = middle
        else:
            low = middle
    needed = math.ceil(high * 100 - 1e-6) / 100
    grade = next(letter for letter in GRADE_CHOICES if GRADE_POINTS[letter] >= needed - 1e-9)
    return TargetPlan(target, open_units, "reachable", needed, grade, _rounded(best))


def _latest_graded(
    record: StudentRecord, catalog: Catalog, extra: Mapping[str, float]
) -> dict[str, tuple[float, float]]:
    """Units and grade points of the latest graded attempt per course, with ``extra`` as the newest."""
    graded = [(a, p) for a in record.attempts if (p := grade_points(a)) is not None]
    latest: dict[str, tuple[float, float]] = {}
    for _index, (attempt, points) in sorted(
        enumerate(graded), key=lambda pair: (pair[1][0].term or EARLIEST, pair[0])
    ):
        latest[attempt.code] = (attempt.units or catalog.units(attempt.code), points)
    for code, points in extra.items():
        latest[code] = (record.units_of(code, catalog), points)
    return latest


def _cgpa(latest: Mapping[str, tuple[float, float]]) -> float | None:
    units = sum(size for size, _ in latest.values())
    return sum(size * points for size, points in latest.values()) / units if units > 0 else None


def _rounded(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None
