"""Program versions by the term a student joined (F0.4)."""

from dataclasses import replace

import pytest

from app.domain.catalog import Catalog, VersionError, choose_version, version_range
from app.domain.terms import Season, Term
from tests.conftest import CS_ID

FALL_2025 = Term(2025, Season.FALL)
FALL_2027 = Term(2027, Season.FALL)


@pytest.fixture
def versions(cs_catalog: Catalog) -> Catalog:
    """The CS major as two versions: from Fall 2025, and from Fall 2027."""
    first = replace(cs_catalog.programs[CS_ID], valid_from=FALL_2025)
    second = replace(first, id=f"{CS_ID}-2027", family=CS_ID, valid_from=FALL_2027)
    programs = {**cs_catalog.programs, first.id: first, second.id: second}
    return Catalog(cs_catalog.courses, cs_catalog.rules, programs)


@pytest.mark.parametrize(
    ("entry", "expected", "how"),
    [
        (FALL_2025, CS_ID, "joined"),
        (Term(2027, Season.SPRING), CS_ID, "joined"),  # the old version, until the new one starts
        (FALL_2027, f"{CS_ID}-2027", "joined"),  # the first term counts
        (Term(2030, Season.SPRING), f"{CS_ID}-2027", "joined"),
        (Term(2024, Season.FALL), CS_ID, "earliest"),  # before every version on file
    ],
)
def test_students_follow_the_version_in_force_when_they_joined(
    versions: Catalog, entry: Term, expected: str, how: str
) -> None:
    choice = choose_version(versions, CS_ID, entry)
    assert (choice.program.id, choice.how) == (expected, how)
    assert [v.id for v in choice.versions] == [CS_ID, f"{CS_ID}-2027"]


def test_a_version_can_be_chosen_and_must_belong_to_the_program(versions: Catalog) -> None:
    choice = choose_version(versions, CS_ID, FALL_2025, chosen=f"{CS_ID}-2027")
    assert (choice.program.id, choice.how) == (f"{CS_ID}-2027", "chosen")
    # A version's own id names the program too.
    assert choose_version(versions, f"{CS_ID}-2027", FALL_2025).program.id == CS_ID
    with pytest.raises(VersionError):
        choose_version(versions, CS_ID, FALL_2025, chosen="minor-psychology")
    with pytest.raises(VersionError):
        choose_version(versions, "no-such-program", FALL_2025)


def test_a_single_version_applies_to_everyone(cs_catalog: Catalog) -> None:
    choice = choose_version(cs_catalog, CS_ID, Term(2020, Season.FALL))
    assert choice.how == "only"
    assert version_range(choice.program, choice.versions) == "every student"


def test_each_version_says_whom_it_applies_to(versions: Catalog) -> None:
    first, second = versions.versions(CS_ID)
    assert version_range(first, [first, second]) == "students who joined from Fall 2025 and before Fall 2027"
    assert version_range(second, [first, second]) == "students who joined from Fall 2027 on"
    start = replace(first, valid_from=None)
    assert version_range(start, [start, second]) == "students who joined before Fall 2027"


def test_students_choose_a_program_not_a_version(versions: Catalog) -> None:
    majors = versions.families("major")
    assert [[v.id for v in family] for family in majors] == [[CS_ID, f"{CS_ID}-2027"]]
