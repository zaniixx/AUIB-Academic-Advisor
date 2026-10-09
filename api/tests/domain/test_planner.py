import time
from collections.abc import Callable
from datetime import date

import pytest

from app.domain.catalog import Catalog, Program, level_courses
from app.domain.planner import (
    ItemKind,
    Lock,
    Pace,
    Plan,
    PlanOptions,
    build_plan,
    building_term,
    eligible_next_term,
    term_choices,
)
from app.domain.recommend import Preferences
from app.domain.record import StudentRecord
from app.domain.requisites import EvalContext, evaluate
from app.domain.terms import Season, Term

from .students import nearly_done, new_student, second_year, with_a_failure

STUDENTS: dict[str, Callable[[], StudentRecord]] = {
    "new": new_student,
    "second-year": second_year,
    "with-a-failure": with_a_failure,
    "nearly-done": nearly_done,
}
OPTIONS = {
    "on-time": PlanOptions(),
    "fastest": PlanOptions(pace=Pace.FASTEST),
    "summers": PlanOptions(include_summer=True),
    "ai-interest": PlanOptions(preferences=Preferences(interests=("ai",), goal="ai_engineer")),
}


def assert_plan_is_valid(
    plan: Plan, program: Program, catalog: Catalog, record: StudentRecord, options: PlanOptions
) -> None:
    completed = set(record.have)
    credits = record.completed_units(catalog) + record.in_progress_units(catalog)
    levels = level_courses(program, catalog)
    for planned in plan.terms:
        limit = options.summer_max_units if planned.term.season is Season.SUMMER else options.max_units
        assert planned.units <= limit, f"{planned.term} is over the unit limit"
        context = EvalContext(frozenset(completed), credits, level_courses=levels)
        same_term = {item.code for item in planned.items if item.code}
        for item in planned.items:
            if item.kind is ItemKind.COURSE and item.code:
                assert catalog.courses[item.code].offered_in(planned.term.season), (
                    f"{item.code} in {planned.term}"
                )
                check = evaluate(catalog.prerequisite(item.code), context)
                assert check.satisfied, f"{item.code} in {planned.term} is missing {check.missing}"
                for rule in catalog.corequisites(item.code):
                    concurrent = EvalContext(frozenset(completed), credits, frozenset(same_term), levels)
                    assert evaluate(rule, concurrent).satisfied
        completed |= same_term
        credits += planned.units
    assert plan.unscheduled == []
    for key, leaf in plan.progress.leaves.items():
        assert leaf.remaining == pytest.approx(plan.slot_units.get(key, 0.0)), (
            f"{leaf.group.label} is left open"
        )
    counted = plan.progress.root.completed + plan.progress.root.in_progress + plan.progress.root.planned
    assert counted + sum(plan.slot_units.values()) == pytest.approx(program.total_units)
    if plan.terms:
        assert plan.graduation_term == plan.terms[-1].term


@pytest.mark.parametrize("student", STUDENTS)
@pytest.mark.parametrize("option_name", OPTIONS)
def test_plans_respect_prerequisites_loads_and_requirements(
    student: str, option_name: str, cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    record, options = STUDENTS[student](), OPTIONS[option_name]
    plan = build_plan(cs_program, cs_catalog, record, options, today)
    assert_plan_is_valid(plan, cs_program, cs_catalog, record, options)


def test_new_student_graduates_on_time_at_a_normal_load(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    plan = build_plan(cs_program, cs_catalog, new_student(), PlanOptions(), today)
    assert plan.start_term == Term(2027, Season.SPRING)
    assert plan.graduation_term == plan.on_time_term == Term(2030, Season.FALL)
    assert all(t.units <= 18 for t in plan.terms)
    assert sum(1 for t in plan.terms if t.units <= 15) >= 5
    first_term = {item.code for item in plan.terms[0].items}
    assert {"CSC 101", "UNI 101", "ENL 101"} <= first_term


def test_fastest_is_never_later_than_on_time(cs_program: Program, cs_catalog: Catalog, today: date) -> None:
    on_time = build_plan(cs_program, cs_catalog, new_student(), PlanOptions(), today)
    fastest = build_plan(cs_program, cs_catalog, new_student(), PlanOptions(pace=Pace.FASTEST), today)
    assert fastest.graduation_term is not None and on_time.graduation_term is not None
    assert fastest.graduation_term <= on_time.graduation_term


def test_plans_are_deterministic(cs_program: Program, cs_catalog: Catalog, today: date) -> None:
    first = build_plan(cs_program, cs_catalog, second_year(), PlanOptions(), today)
    second = build_plan(cs_program, cs_catalog, second_year(), PlanOptions(), today)
    assert [(t.term, [i.key for i in t.items]) for t in first.terms] == [
        (t.term, [i.key for i in t.items]) for t in second.terms
    ]


def test_locked_courses_stay_put(cs_program: Program, cs_catalog: Catalog, today: date) -> None:
    lock = Lock("CSC 233", Term(2027, Season.SPRING))
    plan = build_plan(cs_program, cs_catalog, second_year(), PlanOptions(locks=(lock,)), today)
    assert plan.term_of("CSC 233") == lock.term
    assert next(i for i in plan.terms[0].items if i.code == "CSC 233").locked


SPRING_2027 = Term(2027, Season.SPRING)
FIRST_PICKS = ("CSC 101", "MAT 111", "ENL 101")


def _built_spring(picks: tuple[str, ...] = FIRST_PICKS) -> PlanOptions:
    """A student who built Spring 2027 with ``picks`` (F1.9)."""
    return PlanOptions(
        locks=tuple(Lock(code, SPRING_2027) for code in picks), built_terms=frozenset({SPRING_2027})
    )


def test_a_built_term_holds_only_the_students_courses(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    options = _built_spring()
    plan = build_plan(cs_program, cs_catalog, new_student(), options, today)
    first = plan.terms[0]
    assert first.term == SPRING_2027 and first.built
    assert {item.code for item in first.items} == set(FIRST_PICKS)
    assert not any(planned.built for planned in plan.terms[1:])
    # What the app would have added moves to later terms; nothing is lost.
    later = plan.term_of("UNI 101")
    assert later is not None and later > SPRING_2027
    assert building_term(plan) is plan.terms[1]
    assert_plan_is_valid(plan, cs_program, cs_catalog, new_student(), options)


def test_a_term_built_with_no_courses_is_left_empty(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    options = PlanOptions(built_terms=frozenset({SPRING_2027}))
    plan = build_plan(cs_program, cs_catalog, new_student(), options, today)
    assert plan.terms[0].term > SPRING_2027
    assert_plan_is_valid(plan, cs_program, cs_catalog, new_student(), options)


def test_choices_for_the_term_being_built_count_the_terms_before_it(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    record, options = new_student(), _built_spring()
    plan = build_plan(cs_program, cs_catalog, record, options, today)
    planned = building_term(plan)
    assert planned is not None and planned.term == Term(2027, Season.FALL)
    codes = {course.code for course in term_choices(cs_program, cs_catalog, record, options, plan, planned)}
    in_term = {item.code for item in planned.items if item.code}
    assert codes and not codes & in_term and not codes & set(FIRST_PICKS)
    # ENL 201 needs ENL 101, which the student put in the term before.
    assert "ENL 201" in codes
    now = eligible_next_term(cs_program, cs_catalog, record, options, SPRING_2027)
    assert "ENL 201" not in {course.code for course in now}


def test_a_summer_the_student_did_not_plan_offers_only_summer_courses(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    record = second_year()
    suggested = build_plan(cs_program, cs_catalog, record, PlanOptions(), today)
    picks = tuple(item.code for item in suggested.terms[0].items if item.code)
    options = _built_spring(picks)
    plan = build_plan(cs_program, cs_catalog, record, options, today)
    planned = building_term(plan)
    assert planned is not None and planned.term.season is Season.SUMMER
    found = term_choices(cs_program, cs_catalog, record, options, plan, planned)
    assert all(cs_catalog.courses[course.code].summer_only for course in found)
    summers = PlanOptions(include_summer=True, locks=options.locks, built_terms=options.built_terms)
    with_summers = build_plan(cs_program, cs_catalog, record, summers, today)
    summer = building_term(with_summers)
    assert summer is not None
    assert term_choices(cs_program, cs_catalog, record, summers, with_summers, summer)


def test_chosen_courses_are_planned(cs_program: Program, cs_catalog: Catalog, today: date) -> None:
    options = PlanOptions(include=frozenset({"CIN 101", "PSY 334"}))
    plan = build_plan(cs_program, cs_catalog, second_year(), options, today)
    assert plan.term_of("CIN 101") is not None
    assert plan.term_of("PSY 334") is not None
    assert_plan_is_valid(plan, cs_program, cs_catalog, second_year(), options)


def test_locking_a_course_too_early_is_reported(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    lock = Lock("CSC 450", Term(2027, Season.SPRING))
    plan = build_plan(cs_program, cs_catalog, second_year(), PlanOptions(locks=(lock,)), today)
    assert plan.term_of("CSC 450") == lock.term
    assert any("CSC 450 is locked" in issue.message for issue in plan.issues)


def test_interests_choose_matching_electives(cs_program: Program, cs_catalog: Catalog, today: date) -> None:
    options = PlanOptions(preferences=Preferences(interests=("ai",), goal="ai_engineer"))
    plan = build_plan(cs_program, cs_catalog, new_student(), options, today)
    chosen = {i.code for t in plan.terms for i in t.items if i.reason.startswith("Major elective")}
    assert "CSC 333" in chosen  # Machine Learning
    assert all(i.reason for t in plan.terms for i in t.items)


def test_electives_do_not_delay_graduation(cs_program: Program, cs_catalog: Catalog, today: date) -> None:
    for interests in [("ai",), ("bio",), ("security",), ()]:
        options = PlanOptions(preferences=Preferences(interests=interests))
        plan = build_plan(cs_program, cs_catalog, new_student(), options, today)
        assert plan.graduation_term == Term(2030, Season.FALL), interests


def test_each_open_choice_slot_suggests_different_courses(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    plan = build_plan(cs_program, cs_catalog, new_student(), PlanOptions(), today)
    free = [
        i for t in plan.terms for i in t.items if i.kind is ItemKind.SLOT and "Free" in (i.group_label or "")
    ]
    assert len(free) == 4
    assert all(slot.suggestions for slot in free)
    assert len({code for slot in free for code in slot.suggestions}) == sum(len(s.suggestions) for s in free)


def test_placement_conditions_are_reported_not_blocking(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    plan = build_plan(cs_program, cs_catalog, new_student(), PlanOptions(), today)
    assert any(issue.code == "MAT 130" and "Placement" in issue.message for issue in plan.issues)


def test_plan_is_fast_enough(cs_program: Program, cs_catalog: Catalog, today: date) -> None:
    """F1.5 asks for results in under 2 seconds; leave a wide margin for slower servers."""
    started = time.perf_counter()
    for _ in range(5):
        build_plan(cs_program, cs_catalog, new_student(), PlanOptions(), today)
    assert (time.perf_counter() - started) / 5 < 0.5


def test_nearly_done_student_finishes_next_term(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    plan = build_plan(cs_program, cs_catalog, nearly_done(), PlanOptions(), today)
    assert plan.graduation_term == Term(2027, Season.SPRING)
    assert plan.terms[0].term == Term(2027, Season.SPRING)


@pytest.mark.parametrize("student", STUDENTS)
def test_eligible_courses_have_no_unmet_prerequisites(
    student: str, cs_program: Program, cs_catalog: Catalog
) -> None:
    record = STUDENTS[student]()
    context = EvalContext(
        record.have,
        record.completed_units(cs_catalog) + record.in_progress_units(cs_catalog),
        level_courses=level_courses(cs_program, cs_catalog),
    )
    eligible = eligible_next_term(cs_program, cs_catalog, record, PlanOptions())
    assert eligible
    for course in eligible:
        assert course.code not in record.have
        assert evaluate(cs_catalog.prerequisite(course.code), context).satisfied, course.code


def test_new_student_can_start_with_the_intro_courses(cs_program: Program, cs_catalog: Catalog) -> None:
    eligible = {
        course.code for course in eligible_next_term(cs_program, cs_catalog, new_student(), PlanOptions())
    }
    assert {"CSC 101", "MAT 111", "UNI 101"} <= eligible
    assert "CSC 231" not in eligible


@pytest.mark.parametrize("student", ["new", "second-year"])
@pytest.mark.parametrize("include_summer", [False, True])
def test_internships_are_planned_in_summer(
    student: str, include_summer: bool, cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    options = PlanOptions(include_summer=include_summer)
    plan = build_plan(cs_program, cs_catalog, STUDENTS[student](), options, today)
    for code in ("CSC 390", "CSC 391"):
        term = plan.term_of(code)
        assert term is not None, code
        assert term.season is Season.SUMMER, f"{code} planned in {term}"
    if not include_summer:
        summer_courses = {i.code for t in plan.terms if t.term.season is Season.SUMMER for i in t.items}
        assert summer_courses == {"CSC 390", "CSC 391"}


def test_internships_are_eligible_only_for_a_summer_term(cs_program: Program, cs_catalog: Catalog) -> None:
    record = second_year()  # 45 credits once this term ends: sophomore standing
    spring = eligible_next_term(cs_program, cs_catalog, record, PlanOptions(), Term(2027, Season.SPRING))
    summer = eligible_next_term(cs_program, cs_catalog, record, PlanOptions(), Term(2027, Season.SUMMER))
    assert "CSC 390" not in {c.code for c in spring}
    assert "CSC 390" in {c.code for c in summer}


@pytest.mark.parametrize("student", STUDENTS)
def test_replacement_options_follow_the_rules(
    student: str, cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    record = STUDENTS[student]()
    options = PlanOptions(preferences=Preferences(interests=("ai",)))
    plan = build_plan(cs_program, cs_catalog, record, options, today)
    groups = {g.key: g for g in cs_program.leaf_groups()}
    levels = level_courses(cs_program, cs_catalog)
    planned = {i.code for t in plan.terms for i in t.items if i.code}
    completed = set(record.have)
    credits = record.completed_units(cs_catalog) + record.in_progress_units(cs_catalog)
    offered_any = False
    for term in plan.terms:
        before = EvalContext(frozenset(completed), credits, level_courses=levels)
        same_term = {i.code for i in term.items if i.code}
        for item in term.items:
            if not item.alternatives:
                continue
            offered_any = True
            group = groups[item.group_key or ""]
            for code in item.alternatives:
                course = cs_catalog.courses[code]
                assert group.is_open_pool or code in group.courses
                assert code not in planned
                assert code not in record.have
                assert course.offered_in(term.term.season)
                assert evaluate(cs_catalog.prerequisite(code), before).satisfied, (code, term.term)
                others = frozenset(same_term - {item.code})
                concurrent = EvalContext(frozenset(completed), credits, others, levels)
                assert all(evaluate(rule, concurrent).satisfied for rule in cs_catalog.corequisites(code))
        completed |= same_term
        credits += term.units
    assert offered_any


def test_courses_other_courses_need_cannot_be_replaced(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    plan = build_plan(cs_program, cs_catalog, new_student(), PlanOptions(), today)
    items = {i.code: i for t in plan.terms for i in t.items if i.code}
    assert items["CSC 231"].alternatives == ()  # a required core course
    assert items["MAT 111"].alternatives == ()  # needed before CSC 231 and MAT 112


def test_replacing_an_elective_keeps_the_plan_valid(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    options = PlanOptions(preferences=Preferences(interests=("ai",)))
    plan = build_plan(cs_program, cs_catalog, new_student(), options, today)
    term, item = next((t, i) for t in plan.terms for i in t.items if i.code and i.alternatives)
    choice = item.alternatives[0]
    replaced = PlanOptions(
        preferences=options.preferences,
        exclude=frozenset({item.code or ""}),
        locks=(Lock(choice, term.term),),
    )
    after = build_plan(cs_program, cs_catalog, new_student(), replaced, today)
    assert after.term_of(choice) == term.term
    assert after.term_of(item.code or "") is None
    assert_plan_is_valid(after, cs_program, cs_catalog, new_student(), replaced)
