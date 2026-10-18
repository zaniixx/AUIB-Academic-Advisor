"""The course data sealed for the public repository (ADR 0008)."""

import base64
import shutil
import tempfile
from pathlib import Path

import pytest

from app import cli
from app.services import sealed_data
from app.services.sealed_data import SealError
from app.settings import REPO_ROOT, get_settings
from tests.conftest import COURSES_FILE, CS_PACKAGE

KEY = sealed_data.parse_key(sealed_data.new_key())


def _plain_tree(root: Path) -> None:
    (root / "data" / "catalog").mkdir(parents=True)
    shutil.copy(COURSES_FILE, root / "data" / "catalog" / "courses.json")
    shutil.copytree(CS_PACKAGE, root / "data" / "programs" / CS_PACKAGE.name)
    (root / "scripts" / "curricula").mkdir(parents=True)
    (root / "scripts" / "curricula" / "build.py").write_text("PROGRAMS = []\n", encoding="utf-8")


def test_sealed_data_round_trips_and_resealing_unchanged_files_changes_nothing(tmp_path: Path) -> None:
    _plain_tree(tmp_path / "plain")
    sealed = tmp_path / "curriculum.sealed"
    assert sealed_data.seal_folder(tmp_path / "plain", sealed, KEY) == 4
    blob = sealed.read_bytes()
    assert b"CSC" not in blob and b"courses" not in blob  # nothing readable without the key

    assert sealed_data.seal_folder(tmp_path / "plain", sealed, KEY) is None
    assert sealed.read_bytes() == blob  # git sees no change

    sealed_data.unseal_folder(sealed, KEY, tmp_path / "out")
    assert sealed_data.read_files(tmp_path / "out") == sealed_data.read_files(tmp_path / "plain")


def test_a_wrong_key_or_a_changed_file_is_refused(tmp_path: Path) -> None:
    blob = sealed_data.seal({"data/catalog/courses.json": "[]"}, KEY)
    with pytest.raises(SealError, match="Wrong ADVISOR_DATA_KEY"):
        sealed_data.open_sealed(blob, sealed_data.parse_key(sealed_data.new_key()))
    tampered = blob[:-1] + bytes([blob[-1] ^ 1])
    with pytest.raises(SealError, match="changed or damaged"):
        sealed_data.open_sealed(tampered, KEY)
    with pytest.raises(SealError, match="not a valid key"):
        sealed_data.parse_key("too-short")


def test_unsafe_paths_in_a_sealed_file_are_refused() -> None:
    for name in ("../outside.json", "/etc/passwd", "data/catalog/../../x", "elsewhere/file.json"):
        with pytest.raises(SealError, match="unsafe path"):
            sealed_data.open_sealed(sealed_data.seal({name: "x"}, KEY), KEY)


def test_unsealing_never_overwrites_unsaved_edits_without_force(tmp_path: Path) -> None:
    _plain_tree(tmp_path)
    sealed = tmp_path / "curriculum.sealed"
    sealed_data.seal_folder(tmp_path, sealed, KEY)
    edited = tmp_path / "scripts" / "curricula" / "build.py"
    edited.write_text("PROGRAMS = ['edited']\n", encoding="utf-8")
    with pytest.raises(SealError, match="differ from the sealed copy"):
        sealed_data.unseal_folder(sealed, KEY, tmp_path)
    assert "edited" in edited.read_text(encoding="utf-8")
    sealed_data.unseal_folder(sealed, KEY, tmp_path, force=True)
    assert edited.read_text(encoding="utf-8") == "PROGRAMS = []\n"


def test_the_data_commands_open_the_sealed_copy_when_the_plain_files_are_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _plain_tree(tmp_path / "plain")
    sealed = tmp_path / "curriculum.sealed"
    sealed_data.seal_folder(tmp_path / "plain", sealed, KEY)
    monkeypatch.setenv("ADVISOR_SEALED_DATA", str(sealed))
    monkeypatch.setenv("ADVISOR_COURSES_FILE", str(tmp_path / "absent" / "courses.json"))
    monkeypatch.setenv("ADVISOR_DATA_DIR", str(tmp_path / "absent" / "programs"))
    monkeypatch.setenv("ADVISOR_DATA_KEY", sealed_data.new_key())
    get_settings.cache_clear()
    opened = Path(tempfile.gettempdir())
    before = set(opened.glob("advisor-data-*"))
    try:
        assert cli.main(["validate"]) == 1
        assert "Wrong ADVISOR_DATA_KEY" in capsys.readouterr().err

        monkeypatch.setenv("ADVISOR_DATA_KEY", base64.urlsafe_b64encode(KEY).decode())
        get_settings.cache_clear()
        assert cli.main(["validate"]) == 0
        assert CS_PACKAGE.name in capsys.readouterr().out
        assert set(opened.glob("advisor-data-*")) == before  # the opened copy is deleted again
    finally:
        get_settings.cache_clear()


def test_the_committed_sealed_copy_matches_the_plain_files() -> None:
    """Catches plain-file changes that were not sealed (run where the key is available)."""
    settings = get_settings()
    configured = settings.data_key.get_secret_value() if settings.data_key else None
    try:
        key = sealed_data.find_key(configured, REPO_ROOT)
    except SealError:
        pytest.skip("No ADVISOR_DATA_KEY here")
    sealed = sealed_data.open_sealed(settings.sealed_data.read_bytes(), key)
    assert sealed == sealed_data.read_files(REPO_ROOT), "Run: python -m app.cli data-seal"


def test_the_key_is_read_from_the_environment_or_else_from_dot_env(tmp_path: Path) -> None:
    key = sealed_data.new_key()
    with pytest.raises(SealError, match=r"Set ADVISOR_DATA_KEY in .env"):
        sealed_data.find_key(None, tmp_path)
    (tmp_path / ".env").write_text(
        f'POSTGRES_PASSWORD=x\n# a comment\nADVISOR_DATA_KEY=\nADVISOR_DATA_KEY="{key}"\n', encoding="utf-8"
    )
    assert sealed_data.find_key(None, tmp_path) == sealed_data.parse_key(key)
    other = sealed_data.new_key()
    assert sealed_data.find_key(other, tmp_path) == sealed_data.parse_key(other)  # the environment wins
