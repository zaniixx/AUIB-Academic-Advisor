"""Course History paste parsing (F11.3, F11.4).

The pastes below are synthetic: they copy the layout of the SIS Course History
page without any real student's data. Real (anonymised) pastes can be added as
fixture pairs in tests/fixtures/history/ and are checked by the last test.
"""

import json
from pathlib import Path

import pytest

from app.domain.catalog import Catalog
from app.domain.history import parse_course_history
from app.domain.record import AttemptStatus
from app.domain.terms import Season, Term

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "history"

ONE_CELL_PER_LINE = """\
Student Center
Academic Record
Course History
Course
Description
Term
Grade
Units
Status
CSC 101
Introduction to Computer Science
2025/2026 Fall
A
3.00
Taken
Taken
MAT 111
Calculus and Analytic Geometry I
2025/2026 Fall
F
3.00
Taken
MAT 111
Calculus and Analytic Geometry I
2025/2026 Spring
B+
3.00
Taken
ENL 101
Expository Writing
2025/2026 Fall
W
3.00
Withdrawn
CSC 140
Introduction to C Programming
2026/2027 Fall
3.00
In Progress
In Progress
HUM XXX
Transfer Credit Humanities
2025/2026 Fall
TR
3.00
Transferred
Return to Top
See CSC 230 for next steps
"""


@pytest.fixture
def titles(cs_catalog: Catalog) -> dict[str, str]:
    return {code: course.title for code, course in cs_catalog.courses.items()}


def test_one_cell_per_line_paste(titles: dict[str, str]) -> None:
    result = parse_course_history(ONE_CELL_PER_LINE, titles)
    rows = [(r.code, r.term, r.grade, r.units, r.status) for r in result.rows]
    assert rows == [
        ("CSC 101", Term(2025, Season.FALL), "A", 3.0, AttemptStatus.COMPLETED),
        ("MAT 111", Term(2025, Season.FALL), "F", 3.0, AttemptStatus.FAILED),
        ("MAT 111", Term(2026, Season.SPRING), "B+", 3.0, AttemptStatus.COMPLETED),
        ("ENL 101", Term(2025, Season.FALL), "W", 3.0, AttemptStatus.WITHDRAWN),
        ("CSC 140", Term(2026, Season.FALL), None, 3.0, AttemptStatus.IN_PROGRESS),
        ("HUM XXX", Term(2025, Season.FALL), "TR", 3.0, AttemptStatus.COMPLETED),
    ]
    assert [line.text for line in result.unread] == ["See CSC 230 for next steps"]
    assert result.ignored_line_count >= 3


def test_tab_separated_rows(titles: dict[str, str]) -> None:
    paste = (
        "Course\tDescription\tTerm\tGrade\tUnits\tStatus\n"
        "CSC 101\tIntroduction to Computer Science\t2025/2026 Fall\tA-\t3.00\tTaken\n"
        "STA 210\tApplied Probability and Statistics\t2026/2027 Fall\t\t3.00\tIn Progress\n"
    )
    result = parse_course_history(paste, titles)
    assert [(r.code, r.grade, r.status) for r in result.rows] == [
        ("CSC 101", "A-", AttemptStatus.COMPLETED),
        ("STA 210", None, AttemptStatus.IN_PROGRESS),
    ]
    assert result.rows[1].title == "Applied Probability and Statistics"


def test_whole_row_on_one_line(titles: dict[str, str]) -> None:
    result = parse_course_history(
        "CSC 101 Introduction to Computer Science 2025/2026 Fall A 3.00 Taken", titles
    )
    assert [(r.code, r.term, r.grade, r.status) for r in result.rows] == [
        ("CSC 101", Term(2025, Season.FALL), "A", AttemptStatus.COMPLETED)
    ]


def test_rows_that_need_a_decision_carry_issues(titles: dict[str, str]) -> None:
    paste = "CSC 230\nObject-Oriented Computing\n2026/2027 Fall\n3.00\nZZZ 101\nMystery Course\n2025/2026 Fall\nA\n3.00\nTaken"
    rows = parse_course_history(paste, titles).rows
    assert rows[0].status is None
    assert any("Status not shown" in issue for issue in rows[0].issues)
    assert any("Not in the catalog" in issue for issue in rows[1].issues)


def test_duplicate_rows_are_removed_and_counted(titles: dict[str, str]) -> None:
    row = "CSC 101\nIntroduction to Computer Science\n2025/2026 Fall\nA\n3.00\nTaken\n"
    result = parse_course_history(row + row, titles)
    assert len(result.rows) == 1
    assert result.duplicates_removed == 1


def test_repeated_attempts_do_not_count(titles: dict[str, str]) -> None:
    paste = "MAT 111\nCalculus I\n2025/2026 Fall\nD\n3.00\nRepeated\n"
    row = parse_course_history(paste, titles).rows[0]
    assert row.status is AttemptStatus.NOT_COUNTED


def test_empty_paste() -> None:
    result = parse_course_history("", {})
    assert result.rows == [] and result.unread == [] and result.ignored_line_count == 0


@pytest.mark.parametrize("paste_file", sorted(FIXTURES.glob("*.txt")), ids=lambda p: p.stem)
def test_fixture_pastes(paste_file: Path, titles: dict[str, str]) -> None:
    expected = json.loads(paste_file.with_suffix(".expected.json").read_text(encoding="utf-8"))
    result = parse_course_history(paste_file.read_text(encoding="utf-8"), titles)
    found = [
        {"code": r.code, "term": r.term.label if r.term else None, "grade": r.grade, "status": r.status}
        for r in result.rows
    ]
    assert found == expected
