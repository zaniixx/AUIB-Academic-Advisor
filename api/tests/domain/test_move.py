"""Moving a planned course to another term (F6.1): valid moves show their effect, invalid ones say why."""

from datetime import date

import pytest

from app.domain.catalog import Catalog, Course, Group, GroupRole, Program, Rule
from app.domain.planner import Lock, PlanOptions
from app.domain.record import build_record
from app.domain.requisites import CourseReq, ParseStatus, RuleKind
from app.domain.terms import Season, Term
from app.domain.whatif import WhatIfError, move_course, move_options, moved_options

from .students import second_year

SPRING_2027 = Term(2027, Season.SPRING)
FALL_2027 = Term(2027, Season.FALL)
SPRING_2028 = Term(2028, Season.SPRING)


def _program(
    codes: tuple[str, ...], rules: dict[str, dict[RuleKind, Rule]] | None = None
) -> tuple[Program, Catalog]:
    """A major whose core is ``codes``, three credits each."""
    courses = {code: Course(code, f"Course {code}", 3.0) for code in codes}
    total = 3.0 * len(codes)
    core = Group("core", "Core", "Core", total, GroupRole.CORE, codes)
    program = Program("test", "Test", "major", total, Group("root", "Test", "Test", total, children=(core,)))
    return program, Catalog(courses, rules or {}, {"test": program})


def _rule(code: str, kind: RuleKind, needs: str) -> dict[RuleKind, Rule]:
    return {kind: Rule(code, kind, needs, CourseReq(needs), ParseStatus.PARSED)}


def _chain() -> tuple[Program, Catalog]:
    """ABC 101 -> ABC 201 -> ABC 301: one course a term."""
    return _program(
        ("ABC 101", "ABC 201", "ABC 301"),
        {
            "ABC 201": _rule("ABC 201", RuleKind.PRE, "ABC 101"),
            "ABC 301": _rule("ABC 301", RuleKind.PRE, "ABC 201"),
        },
    )


def test_a_valid_move_shows_the_new_graduation_and_what_shifts(today: date) -> None:
    program, catalog = _chain()
    move = move_course(program, catalog, build_record([]), PlanOptions(), "ABC 201", SPRING_2028, today)
    assert move.valid and move.problems == ()
    assert move.graduation_term == Term(2028, Season.FALL)
    assert move.terms_later == 1
    assert [(s.code, s.before, s.after) for s in move.shifts] == [
        ("ABC 201", FALL_2027, SPRING_2028),
        ("ABC 301", SPRING_2028, Term(2028, Season.FALL)),
    ]


def test_moving_a_course_before_its_prerequisite_is_explained(today: date) -> None:
    program, catalog = _chain()
    move = move_course(program, catalog, build_record([]), PlanOptions(), "ABC 301", FALL_2027, today)
    assert not move.valid
    assert move.problems == ("ABC 301 needs ABC 201 done before Fall 2027.",)


def test_moving_a_course_away_from_its_corequisite_is_explained(today: date) -> None:
    program, catalog = _program(("LEC 101", "LAB 101"), {"LAB 101": _rule("LAB 101", RuleKind.CO, "LEC 101")})
    options = PlanOptions(locks=(Lock("LEC 101", FALL_2027), Lock("LAB 101", FALL_2027)))
    move = move_course(program, catalog, build_record([]), options, "LAB 101", SPRING_2027, today)
    assert move.problems == ("LAB 101 needs LEC 101 in Spring 2027 or earlier.",)


def test_a_move_over_the_credit_limit_is_explained(today: date) -> None:
    program, catalog = _program(("ONE 101", "TWO 101"))
    options = PlanOptions(max_units=3.0, preferred_units=3.0, locks=(Lock("ONE 101", SPRING_2027),))
    move = move_course(program, catalog, build_record([]), options, "TWO 101", SPRING_2027, today)
    assert move.problems == (
        "Spring 2027 would have 6 credits, over your limit of 3. Raise the limit in Adjust plan to allow it.",
    )


def test_a_course_that_does_not_run_then_is_not_planned(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    choices = move_options(cs_program, cs_catalog, second_year(), PlanOptions(), "CSC 390", today)
    fall = next(move for move in choices.moves if move.term == FALL_2027)
    assert fall.problems == ("CSC 390 runs in Summer only, not in Fall.",)
    assert fall.graduation_term is None


def test_a_move_must_not_take_away_what_a_placed_course_needs(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    options = PlanOptions(locks=(Lock("CSC 313", FALL_2027),))
    move = move_course(cs_program, cs_catalog, second_year(), options, "CSC 231", SPRING_2028, today)
    assert "You placed CSC 313 in Fall 2027; it would no longer have CSC 231." in move.problems


def test_every_other_term_and_the_one_after_the_plan_are_checked(today: date) -> None:
    program, catalog = _chain()
    choices = move_options(program, catalog, build_record([]), PlanOptions(), "ABC 101", today)
    assert choices.source == SPRING_2027
    assert [move.term for move in choices.moves] == [FALL_2027, SPRING_2028, Term(2028, Season.FALL)]
    # Later than ABC 201 leaves ABC 201 to follow it; the planner moves it, so the move is valid.
    assert all(move.valid for move in choices.moves)
    assert [move.terms_later for move in choices.moves] == [1, 2, 3]


def test_a_term_before_the_plan_starts_cannot_be_chosen(today: date) -> None:
    program, catalog = _chain()
    move = move_course(
        program, catalog, build_record([]), PlanOptions(), "ABC 101", Term(2026, Season.FALL), today
    )
    assert move.problems == ("Fall 2026 has started or passed; your plan starts in Spring 2027.",)


def test_only_courses_in_the_plan_can_move(cs_program: Program, cs_catalog: Catalog, today: date) -> None:
    with pytest.raises(WhatIfError, match="already completed or in progress"):
        move_options(cs_program, cs_catalog, second_year(), PlanOptions(), "CSC 101", today)
    with pytest.raises(WhatIfError, match="not in your plan"):
        move_options(cs_program, cs_catalog, second_year(), PlanOptions(), "ART 101", today)


def test_a_built_term_that_loses_its_last_course_opens_again() -> None:
    options = PlanOptions(
        locks=(Lock("ABC 101", SPRING_2027), Lock("ABC 201", FALL_2027)),
        built_terms=frozenset({SPRING_2027, FALL_2027}),
    )
    moved = moved_options(options, "ABC 101", SPRING_2027, SPRING_2028)
    assert moved.built_terms == frozenset({FALL_2027})
    assert Lock("ABC 101", SPRING_2028) in moved.locks and Lock("ABC 101", SPRING_2027) not in moved.locks
