from __future__ import annotations

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


def pytest_sessionstart(session: pytest.Session) -> None:
    """The tests run against the real course data, which the repository holds sealed (ADR 0008). The app
    itself starts without it; only the tests need it."""
    if not COURSES_FILE.is_file():
        pytest.exit(
            "The tests use the real course data, and data/catalog/ is not on this computer. In api/, run "
            "`python -m app.cli data-unseal` (the key is ADVISOR_DATA_KEY in .env). If data/sealed/ was "
            "deleted too, `git checkout -- ../data/sealed` brings the sealed copy back first.",
            returncode=4,
        )


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
