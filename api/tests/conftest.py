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
