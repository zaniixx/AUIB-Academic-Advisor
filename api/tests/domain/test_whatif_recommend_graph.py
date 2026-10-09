from datetime import date

import pytest

from app.domain.catalog import Catalog, Course, Group, GroupRole, Program, Rule
from app.domain.graph import gateways, longest_chain, prerequisite_graph, program_courses
from app.domain.planner import PlanOptions
from app.domain.recommend import Preferences, open_groups, suggest_for_group
from app.domain.record import build_record
from app.domain.requisites import CourseReq, EvalContext, ParseStatus, RuleKind
from app.domain.terms import Season, Term
from app.domain.whatif import Change, ChangeAction, WhatIfError, what_if

from .students import second_year


def test_dropping_an_in_progress_course_reschedules_it(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    result = what_if(
        cs_program, cs_catalog, second_year(), PlanOptions(), Change("CSC 230", ChangeAction.DROP), today
    )
    assert result.after.term_of("CSC 230") is not None
    moved = {shift.code: shift for shift in result.shifts}
    assert "CSC 230" in moved
    assert "CSC 231" in moved  # depends on CSC 230, so it moves too
    assert moved["CSC 231"].after > moved["CSC 231"].before  # type: ignore[operator]
    assert result.terms_later >= 0


def test_delaying_a_planned_course_moves_it_later(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    result = what_if(
        cs_program, cs_catalog, second_year(), PlanOptions(), Change("CSC 231", ChangeAction.DELAY), today
    )
    before, after = result.before.term_of("CSC 231"), result.after.term_of("CSC 231")
    assert before is not None and after is not None and after > before


def _chain_program() -> tuple[Program, Catalog]:
    """A three-course chain, ABC 101 -> ABC 201 -> ABC 301, with nothing else to take."""
    courses = {code: Course(code, f"Course {code}", 3.0) for code in ("ABC 101", "ABC 201", "ABC 301")}
    rules = {
        "ABC 201": {
            RuleKind.PRE: Rule("ABC 201", RuleKind.PRE, "ABC 101", CourseReq("ABC 101"), ParseStatus.PARSED)
        },
        "ABC 301": {
            RuleKind.PRE: Rule("ABC 301", RuleKind.PRE, "ABC 201", CourseReq("ABC 201"), ParseStatus.PARSED)
        },
    }
    core = Group("core", "Core", "Core", 9.0, GroupRole.CORE, tuple(courses))
    program = Program("chain", "Chain", "major", 9.0, Group("root", "Chain", "Chain", 9.0, children=(core,)))
    return program, Catalog(courses, rules, {"chain": program})


def test_delaying_a_chain_course_delays_graduation(today: date) -> None:
    program, catalog = _chain_program()
    result = what_if(
        program, catalog, build_record([]), PlanOptions(), Change("ABC 201", ChangeAction.DELAY), today
    )
    assert [str(t.term) for t in result.before.terms] == ["Spring 2027", "Fall 2027", "Spring 2028"]
    assert result.after.term_of("ABC 201") == Term(2028, Season.SPRING)
    assert result.after.graduation_term == Term(2028, Season.FALL)
    assert result.terms_later == 1
    assert [(s.code, str(s.before), str(s.after)) for s in result.shifts] == [
        ("ABC 201", "Fall 2027", "Spring 2028"),
        ("ABC 301", "Spring 2028", "Fall 2028"),
    ]


def test_what_if_on_a_course_that_is_not_planned(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    with pytest.raises(WhatIfError):
        what_if(
            cs_program, cs_catalog, second_year(), PlanOptions(), Change("CSC 101", ChangeAction.DELAY), today
        )


def test_every_suggestion_explains_itself(cs_program: Program, cs_catalog: Catalog) -> None:
    record = second_year()
    context = EvalContext(record.have, 30)
    preferences = Preferences(interests=("ai", "culture"), goal="data_scientist")
    for group in open_groups(cs_program, cs_catalog):
        result = suggest_for_group(group, 6, cs_catalog, preferences, context, set(record.have))
        assert result.suggestions, group.label
        for suggestion in result.suggestions:
            assert suggestion.reasons
            assert suggestion.code not in record.have


def test_interests_rank_matching_courses_first(cs_program: Program, cs_catalog: Catalog) -> None:
    group = next(
        g for g in cs_program.leaf_groups() if g.title == "Computer Science- Major Elective - Courses"
    )
    context = EvalContext(frozenset({"CSC 313", "CSC 231", "CSC 230", "MAT 112"}), 60)
    ranked = suggest_for_group(
        group, 12, cs_catalog, Preferences(interests=("ai",)), context, set()
    ).suggestions
    assert ranked[0].code == "CSC 333"  # Machine Learning: matches and is takeable now
    assert "Matches your interest: AI and machine learning" in ranked[0].reasons


def test_gateways_and_longest_chain(cs_program: Program, cs_catalog: Catalog) -> None:
    found = {g.code: g for g in gateways(cs_program, cs_catalog)}
    assert len(found["CSC 101"].dependents) > 20
    assert "CSC 231" in found["CSC 230"].direct_dependents
    chain = longest_chain(prerequisite_graph(cs_catalog, program_courses(cs_program)))
    assert chain[0] == "CSC 101" and len(chain) >= 7
