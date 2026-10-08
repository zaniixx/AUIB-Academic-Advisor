from datetime import date

import pytest

from app.domain.codes import is_placeholder, level_of, normalize_code
from app.domain.terms import Season, Term, current_term, first_planning_term


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CSC 231", "CSC 231"),
        ("csc231", "CSC 231"),
        ("Law 106", "LAW 106"),
        ("TLD204", "TLD 204"),
        ("BIO 101L", "BIO 101L"),
        ("MAT-101A", "MAT 101A"),
        ("ATH 3XX", "ATH 3XX"),
        ("HUM XXX", "HUM XXX"),
        ("HEAL 210", "HEAL 210"),
        ("ASP 6", None),
        ("Introduction", None),
        ("", None),
    ],
)
def test_normalize_code(raw: str, expected: str | None) -> None:
    assert normalize_code(raw) == expected


def test_levels_and_placeholders() -> None:
    assert level_of("CSC 343") == 300
    assert level_of("ATH 3XX") == 300
    assert level_of("HUM XXX") is None
    assert is_placeholder("CHE 2XX")
    assert not is_placeholder("CSC 101")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2024/2025 Fall", Term(2024, Season.FALL)),
        ("2024/2025 Spring", Term(2025, Season.SPRING)),
        ("2024/2025 Summer", Term(2025, Season.SUMMER)),
        ("Fall 2024", Term(2024, Season.FALL)),
        ("Spring Semester 2026", Term(2026, Season.SPRING)),
        ("2026 Summer", Term(2026, Season.SUMMER)),
        ("Winter 2024", None),
        ("Taken", None),
    ],
)
def test_parse_terms(text: str, expected: Term | None) -> None:
    assert Term.parse(text) == expected


def test_term_order_and_navigation() -> None:
    spring, summer, fall = Term(2027, Season.SPRING), Term(2027, Season.SUMMER), Term(2027, Season.FALL)
    assert spring < summer < fall < Term(2028, Season.SPRING)
    assert spring.next() == fall
    assert spring.next(include_summer=True) == summer
    assert fall.next() == Term(2028, Season.SPRING)
    assert fall.academic_year == "2027/2028"
    assert spring.academic_year == "2026/2027"
    assert Term(2026, Season.FALL).regular_terms_until(Term(2030, Season.SPRING)) == 8


def test_current_and_first_planning_term() -> None:
    assert current_term(date(2026, 10, 8)) == Term(2026, Season.FALL)
    assert current_term(date(2026, 3, 1)) == Term(2026, Season.SPRING)
    assert current_term(date(2026, 6, 15)) == Term(2026, Season.SUMMER)
    assert first_planning_term(date(2026, 10, 8), include_summer=False) == Term(2027, Season.SPRING)
    assert first_planning_term(date(2026, 3, 1), include_summer=True) == Term(2026, Season.SUMMER)
    assert first_planning_term(date(2026, 3, 1), include_summer=False) == Term(2026, Season.FALL)
