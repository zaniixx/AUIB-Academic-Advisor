import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app import cli
from app.domain.terms import Season
from app.importer.package import build_courses, load_courses
from app.models import Base
from app.settings import get_settings
from tests.conftest import COURSES_FILE, CS_PACKAGE, PROGRAMS_DIR, PSY_PACKAGE


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = f"sqlite+pysqlite:///{(tmp_path / 'cli.sqlite3').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setenv("ADVISOR_DATABASE_URL", url)
    monkeypatch.setenv("ADVISOR_DATA_DIR", str(PROGRAMS_DIR))
    monkeypatch.setenv("ADVISOR_COURSES_FILE", str(COURSES_FILE))
    get_settings.cache_clear()
    yield url
    get_settings.cache_clear()


def test_validate_checks_the_catalog_and_every_package(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["validate"]) == 0
    output = capsys.readouterr().out
    for program in (
        "course-catalog",
        "casc-computer-science",
        "minor-psychology",
        "minor-teaching-and-learning-design",
    ):
        assert f"{program}: 0 errors" in output
    assert "courses=626" in output


def test_validate_fails_for_a_broken_package(tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    shutil.copytree(CS_PACKAGE, broken)
    (broken / "program.json").write_text('{"id": "Not Valid"}', encoding="utf-8")
    assert cli.main(["validate", str(broken)]) == 1


def test_a_program_listing_a_course_missing_from_the_catalog_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken"
    shutil.copytree(PSY_PACKAGE, broken)
    requirements = json.loads((broken / "requirements.json").read_text(encoding="utf-8"))
    requirements[2]["courses"].append("PSY 999")
    (broken / "requirements.json").write_text(json.dumps(requirements), encoding="utf-8")
    assert cli.main(["validate", str(broken)]) == 1
    assert "missing from the course catalog: PSY 999" in capsys.readouterr().out


def test_import_publishes_only_when_warnings_are_accepted(
    database: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["import", str(CS_PACKAGE)]) == 0
    first = capsys.readouterr().out
    assert "courses_created': 626" in first
    assert "published=False" in first
    assert cli.main(["import", str(CS_PACKAGE), "--accept-warnings"]) == 0
    output = capsys.readouterr().out
    assert "published=True" in output
    assert "courses_unchanged': 626" in output


def test_import_all_only_if_empty(database: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["import-all", "--only-if-empty", "--accept-warnings"]) == 0
    assert "imported, published=True" in capsys.readouterr().out
    assert cli.main(["import-all", "--only-if-empty"]) == 0
    assert "nothing to do" in capsys.readouterr().out


def test_import_all_only_new_adds_programs_added_later(
    database: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["import", str(CS_PACKAGE), "--accept-warnings"]) == 0
    capsys.readouterr()
    assert cli.main(["import-all", "--only-new", "--accept-warnings"]) == 0
    output = capsys.readouterr().out
    assert "minor-psychology: 0 errors" in output
    assert "minor-teaching-and-learning-design: 0 errors" in output
    assert "casc-computer-science:" not in output
    assert cli.main(["import-all", "--only-new"]) == 0
    assert "No new programs; nothing to do." in capsys.readouterr().out


def test_export_openapi(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"
    assert cli.main(["export-openapi", str(target)]) == 0
    schema = json.loads(target.read_text(encoding="utf-8"))
    assert "/api/v1/planner/plan" in schema["paths"]


def test_unknown_offered_terms_are_rejected(tmp_path: Path) -> None:
    courses = json.loads(COURSES_FILE.read_text(encoding="utf-8"))
    courses["CSC 390"]["offered_terms"] = ["winter"]
    broken = tmp_path / "courses.json"
    broken.write_text(json.dumps(courses), encoding="utf-8")
    assert cli.main(["validate", str(CS_PACKAGE), "--courses", str(broken)]) == 1


def test_catalog_marks_internships_as_summer_only() -> None:
    courses = build_courses(load_courses(COURSES_FILE))
    assert courses["CSC 390"].offered_terms == frozenset({Season.SUMMER})
    assert courses["CSC 231"].offered_terms is None


def test_catalog_is_shared_and_names_no_program() -> None:
    raw = json.loads(COURSES_FILE.read_text(encoding="utf-8"))
    assert len(raw) == 626
    assert not any("requirements" in course for course in raw.values())
    assert not (CS_PACKAGE / "courses.json").exists()
