"""Changing major or minor (F6.3): which completed credits transfer, and when the student would finish."""

from datetime import date

import pytest

from app.domain.catalog import Catalog
from app.domain.planner import Lock, PlanOptions
from app.domain.switch import change_program, counted_units, fresh_options
from app.domain.terms import Season, Term, terms_between
from app.importer.package import CourseList, catalog_from_packages, load_package
from tests.conftest import CS_ID, PACKAGES, PROGRAMS_DIR, PSY_ID

from .students import second_year

PSYCHOLOGY_MAJOR = "casc-psychology"


@pytest.fixture(scope="module")
def two_majors(course_list: CourseList) -> Catalog:
    """The test catalog with a second major to move to."""
    packages = [load_package(path) for path in (*PACKAGES, PROGRAMS_DIR / PSYCHOLOGY_MAJOR)]
    return catalog_from_packages(course_list, packages)


def test_moving_to_another_major_shows_where_each_course_counts(two_majors: Catalog, today: date) -> None:
    record = second_year()
    cs, psychology = two_majors.programs[CS_ID], two_majors.programs[PSYCHOLOGY_MAJOR]
    change = change_program(cs, psychology, two_majors, record, PlanOptions(), today)
    courses = {course.code: course for course in change.courses}
    assert set(courses) == set(record.completed | record.in_progress)
    assert courses["CSC 230"].now == "Major core courses" and courses["CSC 230"].after is None
    assert courses["PSY 101"].after is not None  # a psychology course counts toward the psychology major
    assert courses["ENL 101"].now == courses["ENL 101"].after == "Communication skills"
    assert {course.code for course in change.lost} >= {"CSC 230", "CSC 132"}
    assert "PSY 101" not in {course.code for course in change.lost}
    assert counted_units(change.target) < counted_units(change.current)
    assert change.target.program.id == PSYCHOLOGY_MAJOR
    expected = terms_between(change.current_plan.graduation_term, change.target_plan.graduation_term, False)
    assert change.terms_later == expected


def test_the_new_major_is_planned_fresh(two_majors: Catalog, today: date) -> None:
    cs, psychology = two_majors.programs[CS_ID], two_majors.programs[PSYCHOLOGY_MAJOR]
    options = PlanOptions(locks=(Lock("CSC 231", Term(2027, Season.SPRING)),), max_units=15.0)
    change = change_program(cs, psychology, two_majors, second_year(), options, today)
    assert change.target_plan.term_of("CSC 231") is None  # the CS course placed in the old plan is gone
    assert change.current_plan.term_of("CSC 231") == Term(2027, Season.SPRING)
    fresh = fresh_options(options, psychology)
    assert fresh.locks == () and fresh.max_units == 15.0
    assert fresh.regular_terms_to_graduate == psychology.standard_terms


def test_adding_a_minor_keeps_every_course_and_counts_some_twice(two_majors: Catalog, today: date) -> None:
    cs, minor = two_majors.programs[CS_ID], two_majors.programs[PSY_ID]
    change = change_program(cs, cs, two_majors, second_year(), PlanOptions(), today, target_minor=minor)
    courses = {course.code: course for course in change.courses}
    assert change.lost == ()
    assert courses["PSY 101"].after == "Social science electives"
    assert courses["PSY 101"].after_minor == "Psychology minor: PSY 101 first"
    assert change.target_minor is not None and change.target_minor.root.completed == 3.0
