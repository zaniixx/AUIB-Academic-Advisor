from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from app.domain.catalog import Catalog, Program
from app.importer.package import CourseList, ProgramPackage, catalog_from_packages, load_courses, load_package

REPO_ROOT = Path(__file__).resolve().parents[2]
COURSES_FILE = REPO_ROOT / "data" / "catalog" / "courses.json"
PROGRAMS_DIR = REPO_ROOT / "data" / "programs"
CS_PACKAGE = PROGRAMS_DIR / "casc-computer-science"
PSY_PACKAGE = PROGRAMS_DIR / "minor-psychology"
TLD_PACKAGE = PROGRAMS_DIR / "minor-teaching-and-learning-design"
PACKAGES = (CS_PACKAGE, PSY_PACKAGE, TLD_PACKAGE)
CS_ID = "casc-computer-science"
PSY_ID = "minor-psychology"
TLD_ID = "minor-teaching-and-learning-design"
TODAY = date(2026, 10, 8)  # a fixed "today" keeps plans reproducible


# Fixtures that load the course data; a test using any of them (directly or through another fixture)
# needs it. Tests that read the files themselves carry the ``course_data`` mark.
DATA_FIXTURES = {"course_list", "cs_package", "cs_catalog", "cs_program", "make_client", "database"}


def has_course_data() -> bool:
    return COURSES_FILE.is_file()


def pytest_sessionstart(session: pytest.Session) -> None:
    """Most tests run against the real course data, which the repository holds sealed (ADR 0008). CI on
    GitHub runs without it (the key is not given to GitHub), and those tests are skipped there; they run
    on a maintainer's computer. Locally, missing data stops the run, so a mostly skipped run is not
    mistaken for a passing one."""
    if not has_course_data() and not os.environ.get("CI"):
        pytest.exit(
            "The tests use the real course data, and data/catalog/ is not on this computer. In api/, run "
            "`python -m app.cli data-unseal` (the key is ADVISOR_DATA_KEY in .env). If data/sealed/ was "
            "deleted too, `git checkout -- ../data/sealed` brings the sealed copy back first.",
            returncode=4,
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if has_course_data():
        return
    skip = pytest.mark.skip(reason="needs the course data, which is not here (CI on GitHub runs without it)")
    for item in items:
        if DATA_FIXTURES & set(getattr(item, "fixturenames", ())) or item.get_closest_marker("course_data"):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def course_list() -> CourseList:
    return load_courses(COURSES_FILE)


@pytest.fixture(scope="session")
def cs_package() -> ProgramPackage:
    return load_package(CS_PACKAGE)


@pytest.fixture(scope="session")
def cs_catalog(course_list: CourseList) -> Catalog:
    """The shared course catalog with every program package: the CS major and both minors."""
    return catalog_from_packages(course_list, [load_package(path) for path in PACKAGES])


@pytest.fixture(scope="session")
def cs_program(cs_catalog: Catalog) -> Program:
    return cs_catalog.programs[CS_ID]


@pytest.fixture
def today() -> date:
    return TODAY
