import pytest

from app.domain.catalog import Catalog
from app.domain.gpa import gpa_summary
from app.domain.record import Attempt, AttemptStatus, build_record
from app.domain.terms import Season, Term

FALL_2025 = Term(2025, Season.FALL)
SPRING_2026 = Term(2026, Season.SPRING)
FALL_2026 = Term(2026, Season.FALL)


def done(code: str, grade: str, term: Term = FALL_2025, units: float = 3.0) -> Attempt:
    status = AttemptStatus.FAILED if grade in ("F", "WF") else AttemptStatus.COMPLETED
    return Attempt(code, status, term, grade, units)


def test_cumulative_and_last_term(cs_catalog: Catalog) -> None:
    record = build_record(
        [
            done("CSC 101", "A"),
            done("MAT 111", "C"),
            done("CSC 140", "B+", SPRING_2026),
            done("ENL 101", "B-", SPRING_2026),
        ]
    )
    summary = gpa_summary(record, cs_catalog)
    assert summary is not None
    assert summary.cumulative == pytest.approx((4.0 + 2.0 + 3.3 + 2.7) / 4, abs=0.005)
    assert summary.last_term is not None
    assert summary.last_term.term == SPRING_2026
    assert summary.last_term.gpa == pytest.approx(3.0)


def test_a_retake_replaces_the_earlier_grade(cs_catalog: Catalog) -> None:
    record = build_record([done("CSC 101", "A"), done("MAT 112", "F"), done("MAT 112", "B", SPRING_2026)])
    summary = gpa_summary(record, cs_catalog)
    assert summary is not None
    assert summary.cumulative == pytest.approx(3.5)
    assert summary.units == 6


def test_grades_without_points_are_left_out(cs_catalog: Catalog) -> None:
    record = build_record(
        [
            done("CSC 101", "A"),
            Attempt("HUM XXX", AttemptStatus.COMPLETED, FALL_2025, "TR", 3.0),
            Attempt("PHI 101", AttemptStatus.WITHDRAWN, FALL_2025, "W", 3.0),
            Attempt("CSC 230", AttemptStatus.IN_PROGRESS, FALL_2026, None, 3.0),
            Attempt("MAT 111", AttemptStatus.NOT_COUNTED, FALL_2025, "D", 3.0),  # SIS "Repeated"
            done("LIT 101", "WF"),
        ]
    )
    summary = gpa_summary(record, cs_catalog)
    assert summary is not None
    assert summary.cumulative == pytest.approx(2.0)  # A and WF (counted as F)


def test_retakes_that_raise_the_cgpa_most_come_first(cs_catalog: Catalog) -> None:
    record = build_record(
        [
            done("CSC 101", "A"),
            done("MAT 111", "D"),
            done("ENL 101", "C+"),
            done("HIS 101", "B"),
            done("CSC 140", "F"),
        ]
    )
    summary = gpa_summary(record, cs_catalog, in_plan={"CSC 140"})
    assert summary is not None
    assert [r.code for r in summary.retakes] == ["CSC 140", "MAT 111", "ENL 101"]
    first = summary.retakes[0]
    assert first.in_plan
    assert first.with_a == pytest.approx((4.0 + 1.0 + 2.3 + 3.0 + 4.0) / 5, abs=0.005)
    assert first.with_a > first.with_b > summary.cumulative
    assert "HIS 101" not in {r.code for r in summary.retakes}  # a B is not suggested


def test_no_grades_means_no_gpa(cs_catalog: Catalog) -> None:
    assert gpa_summary(build_record([]), cs_catalog) is None
    in_progress = build_record([Attempt("CSC 101", AttemptStatus.IN_PROGRESS, FALL_2026)])
    assert gpa_summary(in_progress, cs_catalog) is None
