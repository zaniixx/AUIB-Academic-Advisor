"""Reading uploaded tables, the season words admins type, schedules in planning, and backups from the CLI."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select

from app import cli
from app.db import make_engine, make_session_factory
from app.domain.catalog import Catalog
from app.domain.terms import Season, Term
from app.importer.tables import TableError, read_text, read_xlsx
from app.models import AuditLogRow, Base, CourseRow
from app.services.catalog_edit import parse_seasons
from app.settings import get_settings
from tests.conftest import COURSES_FILE, PROGRAMS_DIR


def test_pasted_cells_csv_and_semicolons_read_the_same() -> None:
    for text in (
        "Course Code\tTitle\nCSC 231\tData Structure\n",
        "Course Code,Title\nCSC 231,Data Structure\n",
        "Course Code;Title\nCSC 231;Data Structure\n",
        "﻿\nCourse Code,Title\n\n\nCSC 231,Data Structure\n",
    ):
        table = read_text(text)
        assert table.columns == ["course_code", "title"]
        first = next(iter(table.rows))
        assert (first.pick("course_code"), first.pick("name", "title")) == ("CSC 231", "Data Structure")


def test_quoted_csv_cells_keep_their_commas() -> None:
    table = read_text('code,description\nCSC 231,"Lists, trees, and graphs"\n')
    assert table.rows[0].pick("description") == "Lists, trees, and graphs"
    assert table.rows[0].line == 2


def test_tables_are_bounded() -> None:
    with pytest.raises(TableError, match="empty"):
        read_text("   \n\n")
    with pytest.raises(TableError, match="more than 5000 rows"):
        read_text("code\n" + "CSC 101\n" * 5001)
    with pytest.raises(TableError, match=r"not an \.xlsx"):
        read_xlsx(b"just text")


@pytest.mark.parametrize(
    ("typed", "seasons"),
    [
        ("Fall", ["fall"]),
        ("fall; spring", ["fall", "spring"]),
        ("Spring and Fall", ["fall", "spring"]),
        ("summer only", ["summer"]),
        ("any", None),
        ("Fall and Spring", None),
    ],
)
def test_season_words(typed: str, seasons: list[str] | None) -> None:
    assert parse_seasons(typed) == (seasons, None)


def test_unknown_season_words_are_reported() -> None:
    assert parse_seasons("winter")[1] == "Offered terms must be fall, spring or summer, not 'winter'"


def test_a_published_schedule_decides_what_runs_that_term(cs_catalog: Catalog) -> None:
    spring = Term(2027, Season.SPRING)
    catalog = Catalog(
        cs_catalog.courses, cs_catalog.rules, cs_catalog.programs, schedules={spring: frozenset({"CSC 231"})}
    )
    assert catalog.offered("CSC 231", spring)
    assert not catalog.offered("CSC 101", spring)  # not on the published schedule
    assert catalog.offered("CSC 101", Term(2027, Season.FALL))  # no schedule yet: the usual season rules
    assert not catalog.offered("CSC 390", Term(2027, Season.FALL))  # internships run in summer only
    assert not catalog.offered("ZZZ 101", Term(2027, Season.FALL))


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = f"sqlite+pysqlite:///{(tmp_path / 'backup.sqlite3').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setenv("ADVISOR_DATABASE_URL", url)
    monkeypatch.setenv("ADVISOR_DATA_DIR", str(PROGRAMS_DIR))
    monkeypatch.setenv("ADVISOR_COURSES_FILE", str(COURSES_FILE))
    monkeypatch.setenv("ADVISOR_BACKUP_PASSPHRASE", "a long and private passphrase")
    get_settings.cache_clear()
    yield url
    get_settings.cache_clear()


def test_backups_from_the_command_line(
    database: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["import-all", "--accept-warnings"]) == 0
    backup = tmp_path / "advisor.aab"
    assert cli.main(["backup-export", str(backup)]) == 0
    assert backup.read_bytes().startswith(b"AUIBBAK1")
    assert cli.main(["backup-inspect", str(backup)]) == 0
    assert "courses=821" in capsys.readouterr().out

    factory = make_session_factory(make_engine(database))
    with factory() as session:
        session.get(CourseRow, "CSC 231").title = "Changed after the backup"  # type: ignore[union-attr]
        session.commit()
    assert cli.main(["backup-restore", str(backup)]) == 1  # needs --yes
    assert cli.main(["backup-restore", str(backup), "--yes"]) == 0
    with factory() as session:
        assert session.get(CourseRow, "CSC 231").title == "Data Structure"  # type: ignore[union-attr]
        actions = list(session.scalars(select(AuditLogRow.action).order_by(AuditLogRow.id)))
        assert actions[-1] == "backup.restore"
