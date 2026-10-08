import pytest

from app.domain.catalog import Catalog
from app.domain.requisites import (
    Advisory,
    AdvisoryReq,
    AllOf,
    AnyOf,
    CourseReq,
    CreditsReq,
    EvalContext,
    LevelReq,
    ParseStatus,
    RuleKind,
    RuleSyntaxError,
    Standing,
    StandingReq,
    courses_to_add,
    describe,
    evaluate,
    extract_clauses,
    format_rule,
    from_json,
    parse_description,
    parse_requisite_text,
    parse_rule,
    to_json,
)

SUBJECTS = frozenset(
    {"CSC", "MAT", "STA", "MIS", "PSY", "LAW", "TLD", "PHA", "POL", "CHE", "BIO", "MGT", "PHY"}
)


@pytest.mark.parametrize(
    ("text", "rule", "status"),
    [
        ("CSC 101.", "CSC 101", ParseStatus.PARSED),
        ("CSC 230 and MAT 111", "CSC 230 AND MAT 111", ParseStatus.PARSED),
        ("CSC 231, MAT 112", "CSC 231 AND MAT 112", ParseStatus.PARSED),
        ("MAT 130, MAT 112 and CSC 231", "MAT 130 AND MAT 112 AND CSC 231", ParseStatus.PARSED),
        ("CSC 345 or MIS 201", "CSC 345 OR MIS 201", ParseStatus.PARSED),
        ("PSY 351, OR PSY 352", "PSY 351 OR PSY 352", ParseStatus.PARSED),
        ("Sophomore standing, and MAT 101 or MAT 102", "STANDING(sophomore) AND (MAT 101 OR MAT 102)", ParseStatus.PARSED),
        ("PSY 101, and junior or senior standing", "PSY 101 AND STANDING(junior)", ParseStatus.PARSED),
        ("Junior standing", "STANDING(junior)", ParseStatus.PARSED),
        ("90+ credit hours successfully completed", "CREDITS(90)", ParseStatus.PARSED),
        ("Completion of LAW 220, LAW 224, LAW 240, and a total of 50 credits",
         "LAW 220 AND LAW 224 AND LAW 240 AND CREDITS(50)", ParseStatus.PARSED),
        ("Law 106 & Law 230", "LAW 106 AND LAW 230", ParseStatus.PARSED),
        ("Introduction to Reading, (TLD204) and Introduction to Writing, (TLD 205)",
         "TLD 204 AND TLD 205", ParseStatus.PARSED),
        ("Internship I and II, (TLD 302, 305);", "TLD 302 AND TLD 305", ParseStatus.PARSED),
        ("POL 240 International Organization or POL 312 International Relations",
         "POL 240 OR POL 312", ParseStatus.PARSED),
        ("All major program 300-level classes", "LEVEL(300)", ParseStatus.PARSED),
        ("MGT 610 (recommended)", 'RECOMMENDED("MGT 610")', ParseStatus.PARSED),
        ("Consent of instructor", 'CONSENT("Consent of instructor")', ParseStatus.PARSED),
        ("Senior standing and approval of faculty advisor or head of department",
         'STANDING(senior) AND CONSENT("Approval of faculty advisor or head of department")', ParseStatus.PARSED),
        ("MAT 102 or Mathematics Assessment Test results above a certain cut-off",
         'MAT 102 OR PLACEMENT("Mathematics Assessment Test results above a certain cut-off")', ParseStatus.PARSED),
        ("None", "NONE", ParseStatus.NONE),
        ("Acceptance into the MBA program", 'NOTE("Acceptance into the MBA program")', ParseStatus.UNPARSED),
    ],
)  # fmt: skip
def test_parse_requisite_text(text: str, rule: str, status: ParseStatus) -> None:
    expr, found_status, _unparsed = parse_requisite_text(text, SUBJECTS)
    assert format_rule(expr) == rule
    assert found_status is status


def test_unknown_words_are_kept_as_a_note() -> None:
    expr, status, unparsed = parse_requisite_text("CSC 231 and a portfolio review", SUBJECTS)
    assert status is ParseStatus.PARTIAL
    assert "portfolio review" in unparsed
    assert expr == AllOf((CourseReq("CSC 231"), AdvisoryReq(Advisory.NOTE, "a portfolio review")))


def test_extract_clauses_kinds_and_boundaries() -> None:
    description = (
        "Covers inorganic chemistry. Prerequisite: CHE 101L or CHE 105L.  Prerequisite / Corequisite: CHE 102. "
        "Corequisite: BIO 101 Language of Instruction: English."
    )
    clauses = extract_clauses(description)
    assert [c.kind for c in clauses] == [RuleKind.PRE, RuleKind.PRE_OR_CO, RuleKind.CO]
    assert clauses[2].text.endswith("BIO 101")


def test_description_that_names_this_course_as_a_prerequisite_is_ignored() -> None:
    assert extract_clauses("This course is a prerequisite for all second year law courses.") == []


def test_text_after_the_rule_sentence_is_dropped() -> None:
    rules = parse_description("Prerequisite: CHE 102L.Covers fundamentals of atomic structure", SUBJECTS)
    assert [format_rule(r.expr) for r in rules] == ["CHE 102L"]


def test_cross_listing_is_not_a_requisite() -> None:
    rules = parse_description(
        "Prerequisite: BIO 211. Prerequisite / corequisite: CHE 212. Cross-listed course: CHE 225.", SUBJECTS
    )
    assert {r.kind: format_rule(r.expr) for r in rules} == {
        RuleKind.PRE: "BIO 211",
        RuleKind.PRE_OR_CO: "CHE 212",
    }


@pytest.mark.parametrize(
    "rule",
    [
        "CSC 230",
        "CSC 230 AND MAT 111",
        "CSC 345 OR MIS 201",
        "STANDING(sophomore) AND (MAT 101 OR MAT 102)",
        '(CSC 231 AND MAT 112) OR CONSENT("Instructor approval")',
        "CREDITS(90) AND LEVEL(300)",
        'NOTE("Has a \\"quote\\"")',
        "NONE",
    ],
)
def test_rule_language_round_trip(rule: str) -> None:
    expr = parse_rule(rule)
    assert format_rule(expr) == rule
    assert from_json(to_json(expr)) == expr


def test_rule_language_is_case_insensitive_and_follows_precedence() -> None:
    assert parse_rule("csc230 and mat111 or sta210") == AnyOf(
        (AllOf((CourseReq("CSC 230"), CourseReq("MAT 111"))), CourseReq("STA 210"))
    )


@pytest.mark.parametrize(
    ("rule", "message"),
    [
        ("CSC 230 AND", "ended"),
        ("CSC 230 MAT 111", "Unexpected"),
        ("STANDING(expert)", "freshman, sophomore, junior or senior"),
        ("(CSC 230", "Expected rparen"),
        ("CREDITS(ninety)", "Expected number"),
        ('CONSENT("")', "needs some text"),
        ("CSC 230 # MAT 111", "Unexpected character"),
    ],
)
def test_rule_language_errors(rule: str, message: str) -> None:
    with pytest.raises(RuleSyntaxError, match=message):
        parse_rule(rule)


def _context(completed: set[str], credits: float = 0, concurrent: set[str] | None = None) -> EvalContext:
    return EvalContext(
        completed=frozenset(completed),
        credits=credits,
        concurrent=frozenset(concurrent or ()),
        level_courses={300: frozenset({"CSC 313", "CSC 343"})},
    )


def test_evaluate() -> None:
    rule = parse_rule("CSC 230 AND (MAT 111 OR MAT 102)")
    assert evaluate(rule, _context({"CSC 230", "MAT 102"})).satisfied
    result = evaluate(rule, _context({"MAT 111"}))
    assert not result.satisfied
    assert result.missing == ("CSC 230",)


def test_standing_and_credits_use_completed_credits() -> None:
    assert not evaluate(StandingReq(Standing.JUNIOR), _context(set(), credits=59)).satisfied
    assert evaluate(StandingReq(Standing.JUNIOR), _context(set(), credits=60)).satisfied
    assert evaluate(CreditsReq(90), _context(set(), credits=90)).satisfied


def test_advisory_alternatives_never_block_but_are_reported() -> None:
    rule = parse_rule('MAT 102 OR PLACEMENT("Math assessment")')
    clean = evaluate(rule, _context({"MAT 102"}))
    assert clean.satisfied and clean.advisories == ()
    flagged = evaluate(rule, _context(set()))
    assert flagged.satisfied
    assert flagged.advisories == ("Placement: Math assessment",)


def test_corequisites_accept_courses_in_the_same_term() -> None:
    assert evaluate(CourseReq("BIO 101"), _context(set(), concurrent={"BIO 101"})).satisfied


def test_level_rule_needs_every_course_at_that_level() -> None:
    assert not evaluate(LevelReq(300), _context({"CSC 313"})).satisfied
    assert evaluate(LevelReq(300), _context({"CSC 313", "CSC 343"})).satisfied


def test_courses_to_add_picks_the_cheapest_alternative() -> None:
    rule = parse_rule("CSC 230 AND (MIS 201 OR CSC 345)")
    cost = {"CSC 345": 0.5}.get
    assert courses_to_add(rule, frozenset({"CSC 230"}), {}, lambda c: cost(c) or 1.0) == {"CSC 345"}
    placement = parse_rule('MAT 102 OR PLACEMENT("test")')
    assert courses_to_add(placement, frozenset(), {}, lambda _c: 1.0) == frozenset()


def test_describe_is_plain_english() -> None:
    assert describe(parse_rule("STANDING(junior) AND (CSC 345 OR MIS 201)")) == (
        "Junior standing (60+ credits) and (CSC 345 or MIS 201)"
    )


def test_whole_cs_catalog_parses(cs_catalog: Catalog) -> None:
    """Proxy for the 95% prerequisite-accuracy target: nearly every rule parses without leftovers."""
    rules = [rule for by_kind in cs_catalog.rules.values() for rule in by_kind.values()]
    understood = [r for r in rules if r.status in (ParseStatus.PARSED, ParseStatus.NONE)]
    assert len(rules) > 300
    assert len(understood) / len(rules) >= 0.99
    assert cs_catalog.prerequisite("CSC 499") == LevelReq(300)
    assert format_rule(cs_catalog.prerequisite("CSC 231")) == "CSC 230 AND MAT 111"
