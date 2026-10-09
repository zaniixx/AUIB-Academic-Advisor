"""The quick questions about interests, dislikes and plans (F2.1), and how their answers rank electives."""

import pytest

from app.domain.catalog import Catalog
from app.domain.questions import questions_for
from app.domain.recommend import Preferences, rank_courses
from app.domain.requisites import EvalContext
from app.importer.package import CourseList, catalog_from_packages, load_package

from ..conftest import PROGRAMS_DIR

NEW_STUDENT = EvalContext(completed=frozenset(), credits=0)


@pytest.fixture(scope="module")
def catalog(course_list: CourseList) -> Catalog:
    packages = [
        load_package(path) for path in sorted(PROGRAMS_DIR.iterdir()) if (path / "program.json").is_file()
    ]
    return catalog_from_packages(course_list, packages)


def _questions(catalog: Catalog, program_id: str) -> dict[str, list[str]]:
    return {q.id: [o.id for o in q.options] for q in questions_for(catalog.programs[program_id], catalog)}


def test_questions_follow_the_major(catalog: Catalog) -> None:
    cs = _questions(catalog, "casc-computer-science")
    assert list(cs) == ["major_areas", "topics", "avoid", "plans", "goal"]
    assert {"software", "ai", "data"} <= set(cs["major_areas"])
    assert cs["goal"][0] == "software_engineer" and cs["goal"][-1] == "undecided"

    english = _questions(catalog, "casc-english-literature")
    assert {"languages", "creative", "middle_east"} <= set(english["major_areas"])
    assert "translator" in english["goal"]
    assert not {"ai", "software", "health"} & set(english["major_areas"])

    relations = _questions(catalog, "cis-international-relations")
    assert {"diplomacy", "rights_policy"} <= set(relations["major_areas"])
    assert relations["goal"][:2] == ["diplomat", "policy_analyst"]


def test_a_major_with_no_choices_asks_only_the_general_questions(catalog: Catalog) -> None:
    # Accounting and Dentistry list every course; only the core liberal arts leave a choice.
    for program_id in ("cob-accounting", "cod-dental-surgery"):
        assert list(_questions(catalog, program_id)) == ["topics", "avoid", "plans"]


def test_the_direction_is_asked_only_after_work_or_graduate_school(catalog: Catalog) -> None:
    goal = next(q for q in questions_for(catalog.programs["casc-psychology"], catalog) if q.id == "goal")
    assert goal.show_if == ("plans", ("work", "grad_school"))
    assert goal.kind == "single"


def test_courses_mentioning_what_the_student_avoids_come_later(catalog: Catalog) -> None:
    pool = ["ENL 101", "PHI 101", "HIS 101"]  # ENL 101's description is about writing essays
    plain = {s.code: s for s in rank_courses(pool, catalog, Preferences(), NEW_STUDENT)}
    avoiding = {s.code: s for s in rank_courses(pool, catalog, Preferences(avoid=("essays",)), NEW_STUDENT)}
    assert avoiding["ENL 101"].score < plain["ENL 101"].score
    assert (
        "Its description mentions essays or papers, which you would rather avoid"
        in avoiding["ENL 101"].reasons
    )
    assert avoiding["PHI 101"].score == plain["PHI 101"].score


def test_plans_after_graduation_raise_the_courses_that_help(catalog: Catalog) -> None:
    pool = ["PSY 360", "PSY 226", "PSY 324"]  # electives; none about research methods
    pool += ["PSY 301"]  # Research Methods in Psychology
    ranked = rank_courses(pool, catalog, Preferences(plans="grad_school"), NEW_STUDENT)
    best = ranked[0]
    assert best.code == "PSY 301"
    assert "Useful for graduate school" in best.reasons
