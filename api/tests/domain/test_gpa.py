import pytest

from app.domain.catalog import Catalog
from app.domain.gpa import gpa_summary, grades_for_target, project_gpa
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


def now(code: str, units: float = 3.0) -> Attempt:
    return Attempt(code, AttemptStatus.IN_PROGRESS, FALL_2026, None, units)


def test_expected_grades_project_the_cgpa(cs_catalog: Catalog) -> None:
    # 3.0 over 6 credits now; an A and a C in two 3-credit courses keep it at 3.0.
    record = build_record([done("CSC 101", "A"), done("MAT 111", "C"), now("CSC 230"), now("CSC 132")])
    projection = project_gpa(record, cs_catalog, {"CSC 230": "A", "CSC 132": "C"})
    assert projection.cumulative == pytest.approx(3.0)
    assert projection.courses_gpa == pytest.approx(3.0)
    assert projection.units == 12
    better = project_gpa(record, cs_catalog, {"CSC 230": "A", "CSC 132": "A"})
    assert better.cumulative == pytest.approx((4 + 2 + 4 + 4) / 4)


def test_a_projected_retake_replaces_the_old_grade(cs_catalog: Catalog) -> None:
    record = build_record([done("CSC 101", "A"), done("MAT 112", "F"), now("MAT 112")])
    assert project_gpa(record, cs_catalog, {"MAT 112": "B"}).cumulative == pytest.approx(3.5)


def test_grades_needed_for_a_target(cs_catalog: Catalog) -> None:
    # 2.0 over 6 credits; to reach 2.5 over 12, the 6 open credits must average 3.0 (a B).
    record = build_record([done("CSC 101", "C"), done("MAT 111", "C"), now("CSC 230"), now("CSC 132")])
    plan = grades_for_target(record, cs_catalog, {}, ["CSC 230", "CSC 132"], 2.5)
    assert plan.status == "reachable"
    assert plan.average_needed == pytest.approx(3.0)
    assert plan.grade_needed == "B"
    assert plan.open_units == 6
    # With an A already expected in one course, the other needs only a D (1.0).
    fixed = grades_for_target(record, cs_catalog, {"CSC 230": "A"}, ["CSC 230", "CSC 132"], 2.25)
    assert (fixed.status, fixed.grade_needed, fixed.open_units) == ("reachable", "D", 3)


def test_a_target_can_be_out_of_reach_or_already_met(cs_catalog: Catalog) -> None:
    record = build_record([done("CSC 101", "C"), done("MAT 111", "C"), now("CSC 230")])
    far = grades_for_target(record, cs_catalog, {}, ["CSC 230"], 3.5)
    assert far.status == "out_of_reach"
    assert far.best_possible == pytest.approx((2 + 2 + 4) / 3, abs=0.005)
    met = grades_for_target(record, cs_catalog, {}, ["CSC 230"], 1.0)
    assert met.status == "met"
    assert grades_for_target(record, cs_catalog, {"CSC 230": "B"}, ["CSC 230"], 3.0).status == "no_courses"
