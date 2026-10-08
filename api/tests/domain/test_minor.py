"""Planning a major together with a minor (F11.2).

A course may count toward the major and the minor at the same time (the CEHD minor
flier: "minor courses may meet the requirements of program requirements"), so minor
courses fill the major's free electives and CLA slots before any units are added.
"""

from datetime import date

import pytest

from app.domain.catalog import Catalog, Program, group_requires_all
from app.domain.planner import ItemKind, Plan, PlanOptions, build_plan, eligible_next_term
from app.domain.record import StudentRecord
from tests.conftest import PSY_ID, TLD_ID

from .students import new_student, second_year
from .test_planner import assert_plan_is_valid


def _plan(
    cs_program: Program,
    cs_catalog: Catalog,
    record: StudentRecord,
    minor_id: str | None,
    today: date,
    **options: object,
) -> Plan:
    minor = cs_catalog.programs[minor_id] if minor_id else None
    return build_plan(cs_program, cs_catalog, record, PlanOptions(**options), today, minor)  # type: ignore[arg-type]


@pytest.mark.parametrize("minor_id", [PSY_ID, TLD_ID])
@pytest.mark.parametrize("student", [new_student, second_year])
def test_plans_with_a_minor_cover_it_and_stay_valid(
    cs_program: Program, cs_catalog: Catalog, today: date, minor_id: str, student: object
) -> None:
    record = student()  # type: ignore[operator]
    plan = _plan(cs_program, cs_catalog, record, minor_id, today)
    assert plan.minor_progress is not None
    for leaf in plan.minor_progress.leaves.values():
        assert leaf.remaining <= 0, f"{leaf.group.label} is not covered"
    assert_plan_is_valid(plan, cs_program, cs_catalog, record, PlanOptions())
    assert not plan.unscheduled


def test_minor_courses_count_toward_the_majors_open_choices(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    record = second_year()
    without = _plan(cs_program, cs_catalog, record, None, today)
    with_minor = _plan(cs_program, cs_catalog, record, PSY_ID, today)
    planned = with_minor.course_terms()
    assert {"PSY 210", "PSY 226", "PSY 230", "PSY 240", "PSY 330"} & planned.keys()
    free = next(leaf for leaf in with_minor.progress.leaves.values() if leaf.group.is_open_pool)
    assert any(course.code.startswith("PSY") for course in free.courses)
    # The 15 minor units go into the 12 free-elective units first, so at most one extra course.
    units = lambda plan: sum(term.units for term in plan.terms)  # noqa: E731
    assert units(with_minor) - units(without) <= 3
    assert with_minor.graduation_term == without.graduation_term


def test_required_minor_courses_have_no_replacement_and_choices_stay_in_the_minor(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    plan = _plan(cs_program, cs_catalog, new_student(), TLD_ID, today)
    minor = cs_catalog.programs[TLD_ID]
    items = {item.code: item for term in plan.terms for item in term.items if item.kind is ItemKind.COURSE}
    assert items["TLD 202"].reason == "Required for the Teaching and Learning Design minor"
    assert items["TLD 202"].alternatives == ()
    lists = {
        leaf.label: set(leaf.courses)
        for leaf in minor.leaf_groups()
        if not group_requires_all(leaf, cs_catalog)
    }
    picked = [item for item in items.values() if item.group_label in lists]
    assert picked, "the planner should pick courses from the minor's lists"
    for item in picked:
        assert set(item.alternatives) <= lists[item.group_label]


def test_the_tld_minor_gets_a_400_level_course(cs_program: Program, cs_catalog: Catalog, today: date) -> None:
    plan = _plan(cs_program, cs_catalog, second_year(), TLD_ID, today)
    codes = [code for code in plan.course_terms() if code.startswith("TLD")]
    assert any(code.startswith("TLD 4") for code in codes)
    assert sum(code.startswith("TLD 2") for code in codes) >= 3  # TLD 202 and two more


def test_a_replaced_minor_course_is_swapped_for_another_from_its_list(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    first = _plan(cs_program, cs_catalog, second_year(), PSY_ID, today)
    choice = next(
        code for code in first.course_terms() if code in {"PSY 210", "PSY 226", "PSY 230", "PSY 240"}
    )
    again = _plan(cs_program, cs_catalog, second_year(), PSY_ID, today, exclude=frozenset({choice}))
    assert choice not in again.course_terms()
    assert again.minor_progress is not None
    assert all(leaf.remaining <= 0 for leaf in again.minor_progress.leaves.values())


def test_courses_already_taken_count_toward_the_minor(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    plan = _plan(cs_program, cs_catalog, second_year(), PSY_ID, today)  # second_year() passed PSY 101
    assert plan.minor_progress is not None
    foundation = next(leaf for leaf in plan.minor_progress.leaves.values() if "PSY 101" in leaf.group.courses)
    assert foundation.completed == 3
    assert "PSY 101" not in plan.course_terms()


def test_next_term_lists_courses_for_the_minor(cs_program: Program, cs_catalog: Catalog, today: date) -> None:
    eligible = eligible_next_term(
        cs_program, cs_catalog, new_student(), PlanOptions(), minor=cs_catalog.programs[PSY_ID]
    )
    by_code = {course.code: course for course in eligible}
    assert by_code["PSY 101"].group_label in {"Psychology minor: PSY 101 first", "Social science electives"}
    assert "PSY 210" not in by_code  # needs PSY 101 first
