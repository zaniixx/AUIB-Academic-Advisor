from app.domain.catalog import Catalog, Program
from app.domain.progress import CourseState, allocate, course_flags, whats_left
from app.domain.record import StudentRecord
from tests.conftest import PSY_ID, TLD_ID

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


# F1.7: courses that more than one requirement could use.


def test_a_course_two_requirements_list_counts_once_and_names_the_other(cs_catalog: Catalog) -> None:
    tld = cs_catalog.programs[TLD_ID]
    listing = {leaf.label for leaf in tld.leaf_groups() if "TLD 400" in leaf.courses}
    assert len(listing) == 2
    progress = allocate(tld, cs_catalog, [("TLD 400", 3.0, CourseState.COMPLETED)])
    flags = course_flags(progress)["TLD 400"]
    counted = progress.leaf_for("TLD 400")
    assert counted is not None and flags.counts_toward == counted.group.label
    assert set(flags.also_listed) == listing - {counted.group.label}
    assert flags.also_counts_toward == ()


def test_a_course_counting_toward_the_major_and_the_minor_names_both(
    cs_program: Program, cs_catalog: Catalog
) -> None:
    minor = cs_catalog.programs[PSY_ID]
    major_progress = _progress(cs_program, cs_catalog, second_year())
    minor_progress = _progress(minor, cs_catalog, second_year())
    flags = course_flags(major_progress, minor_progress)["PSY 101"]
    assert flags.counts_toward == "Social science electives"
    assert flags.also_counts_toward == ("Psychology minor: PSY 101 first",)  # the label names the minor
    back = course_flags(minor_progress, major_progress)["PSY 101"]
    assert back.also_counts_toward == ("Social science electives (Computer Science)",)


def test_free_elective_pools_and_single_listings_are_not_flagged(
    cs_program: Program, cs_catalog: Catalog
) -> None:
    flags = course_flags(_progress(cs_program, cs_catalog, second_year()))
    assert all(not found.also_listed and not found.also_counts_toward for found in flags.values())
    assert flags["CSC 140"].counts_toward == "Major core courses"
