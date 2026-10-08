from app.domain.catalog import Catalog, Program
from app.domain.progress import CourseState, allocate, whats_left
from app.domain.record import StudentRecord

from .students import nearly_done, new_student, second_year


def _progress(program: Program, catalog: Catalog, record: StudentRecord):  # type: ignore[no-untyped-def]
    courses = [(c, catalog.units(c), CourseState.COMPLETED) for c in record.completed]
    courses += [(c, catalog.units(c), CourseState.IN_PROGRESS) for c in record.in_progress]
    return allocate(program, catalog, courses)


def _leaf(progress, title_part: str):  # type: ignore[no-untyped-def]
    return next(leaf for leaf in progress.leaves.values() if title_part in leaf.group.title)


def test_group_totals_add_up_to_the_degree(cs_program: Program) -> None:
    assert cs_program.root.units_required == 126
    assert sum(child.units_required for child in cs_program.root.children) == 126


def test_courses_count_toward_the_first_group_that_needs_them(
    cs_program: Program, cs_catalog: Catalog
) -> None:
    progress = _progress(cs_program, cs_catalog, second_year())
    core = _leaf(progress, "CORE- Courses")
    assert {c.code for c in core.courses} == {"CSC 140", "MAT 112", "CSC 230", "CSC 132", "MAT 202"}
    assert core.completed == 6 and core.in_progress == 9
    assert _leaf(progress, "Quantitative Reasoning-MAT").completed == 3  # MAT 111
    assert _leaf(progress, "Humanities").completed == 3  # HIS 101
    assert _leaf(progress, "Natural Sciences").in_progress == 3  # CHE 100


def test_extra_courses_overflow_to_free_electives(cs_program: Program, cs_catalog: Catalog) -> None:
    progress = _progress(cs_program, cs_catalog, nearly_done())
    free = _leaf(progress, "Free Elective-Computer Science-Courses")
    assert {c.code for c in free.courses} == {"MGT 201", "MKT 201"}
    assert progress.not_counted == []


def test_percent_complete_and_whats_left(cs_program: Program, cs_catalog: Catalog) -> None:
    progress = _progress(cs_program, cs_catalog, new_student())
    assert progress.percent_complete == 0
    left = {item.group_label: item for item in whats_left(progress, cs_catalog)}
    assert len(left["Major core courses"].required_courses) == 20
    assert left["Humanities electives"].units_needed == 12
    assert left["Free elective courses"].open_pool


def test_nothing_left_for_completed_groups(cs_program: Program, cs_catalog: Catalog) -> None:
    progress = _progress(cs_program, cs_catalog, nearly_done())
    labels = {item.group_label for item in whats_left(progress, cs_catalog)}
    assert "Communication skills" not in labels
    assert progress.percent_complete > 80
