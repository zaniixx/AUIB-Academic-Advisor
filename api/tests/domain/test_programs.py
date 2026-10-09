"""Every program package in data/programs: it validates, and a new student's plan reaches graduation."""

from datetime import date
from pathlib import Path

import pytest

from app.domain.catalog import Catalog
from app.domain.planner import PlanOptions, build_plan
from app.domain.record import build_record
from app.domain.requisites import course_codes, describe
from app.domain.terms import Season, Term
from app.importer.package import CourseList, ProgramPackage, catalog_from_packages, load_package
from app.importer.validate import validate_package

from ..conftest import PROGRAMS_DIR

PACKAGES = sorted(path for path in PROGRAMS_DIR.iterdir() if (path / "program.json").is_file())


@pytest.fixture(scope="module")
def packages() -> list[ProgramPackage]:
    return [load_package(path) for path in PACKAGES]


@pytest.fixture(scope="module")
def catalog(course_list: CourseList, packages: list[ProgramPackage]) -> Catalog:
    return catalog_from_packages(course_list, packages)


def test_every_package_validates(packages: list[ProgramPackage], catalog: Catalog) -> None:
    assert len(packages) >= 21
    for package in packages:
        report = validate_package(package, catalog)
        assert report.ok, (package.meta.id, [f.message for f in report.errors])


@pytest.mark.parametrize("path", PACKAGES, ids=lambda path: path.name)
def test_a_new_student_can_plan_every_published_major(path: Path, catalog: Catalog, today: date) -> None:
    program = catalog.programs[path.name]
    if program.kind != "major" or not program.published:
        pytest.skip("only published majors are planned on their own")
    options = PlanOptions(max_units=21, regular_terms_to_graduate=program.standard_terms)
    plan = build_plan(program, catalog, build_record([]), options, today)
    assert plan.unscheduled == []
    planned = {item.code for term in plan.terms for item in term.items if item.code}
    assert planned <= set(catalog.courses), "every planned course is in the catalog"
    assert plan.graduation_term is not None and plan.on_time_term is not None
    assert plan.graduation_term <= plan.on_time_term, "a full load finishes within the standard length"
    assert not [issue.message for issue in plan.issues if "still needs" in issue.message]


def test_five_year_degrees_have_ten_regular_semesters(catalog: Catalog, today: date) -> None:
    dentistry = catalog.programs["cod-dental-surgery"]
    assert dentistry.standard_terms == 10 and dentistry.total_units == 189
    assert catalog.programs["casc-biology"].standard_terms == 8
    options = PlanOptions(max_units=21, regular_terms_to_graduate=dentistry.standard_terms)
    plan = build_plan(dentistry, catalog, build_record([]), options, today)
    assert plan.on_time_term == Term(2031, Season.FALL)  # ten Fall and Spring terms from Spring 2027


def test_a_prerequisite_missing_from_the_catalog_is_a_note_not_a_course(catalog: Catalog) -> None:
    # SIS lists "PHY 220L" as a prerequisite of PHY 360, but there is no such course.
    assert "PHY 220L" not in catalog.courses
    raw = catalog.rules["PHY 360"]
    assert any("PHY 220L" in course_codes(rule.expr) for rule in raw.values() if rule.expr is not None)
    rule = catalog.prerequisite("PHY 360")
    assert "PHY 220L" not in course_codes(rule)
    assert "Check with your advisor: PHY 220L, which is not in the course catalog" in describe(rule)


def test_courses_added_from_documents_say_where_they_came_from(catalog: Catalog) -> None:
    for code in ("OVS 101", "BDS 200", "ANT 101", "RAD 101", "BDT 210", "HCT 101", "ACC 201"):
        course = catalog.courses[code]
        assert any("not in the SIS course catalog yet" in notice for notice in course.notices), code
    # Internships and practicums the study plans put in summer run only then.
    for code in ("BIO 485", "CHE 352", "PHY 389", "LIT 390", "PSY 480", "OVS 390", "ANT 295", "ANT 399"):
        assert catalog.courses[code].offered_terms == frozenset({Season.SUMMER}), code
