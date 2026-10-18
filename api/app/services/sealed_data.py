"""The course catalog and program data, sealed so the public repository does not publish them (ADR 0008).

Course and program data are for signed-in AUIB students only (F9.1), but the code is public. So the
repository holds one sealed file, ``data/sealed/curriculum.sealed``, instead of the plain files: the
course catalog, the program packages and the curriculum scripts that spell out each program, as JSON,
compressed and encrypted with AES-256-GCM under ``ADVISOR_DATA_KEY`` (32 random bytes, base64), which a
maintainer keeps in the git-ignored ``.env`` at the repository root. The plain files are git-ignored.
``python -m app.cli data-unseal`` writes them from the sealed file, and ``data-seal`` updates the sealed
file after they change. The import commands open the sealed file by
themselves when the plain files are not on disk, as in the Docker images and on Heroku.

File layout (all lengths in bytes):

    8   magic "AUIBDAT1"
    12  AES-GCM nonce
    ..  ciphertext followed by the 16-byte GCM tag; the 20-byte header is authenticated
"""

from __future__ import annotations

import base64
import binascii
import gzip
import json
import os
import secrets
import zlib
from pathlib import Path, PurePosixPath

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"AUIBDAT1"
FORMAT = 1
_NONCE = 12
MAX_UNPACKED_BYTES = 64 * 1024 * 1024
ENV_FILE = ".env"  # at the repository root, git-ignored: where a maintainer keeps ADVISOR_DATA_KEY

# What is sealed, relative to the repository root. The images need only the first two.
SEALED_PATHS = ("data/catalog", "data/programs", "scripts/curricula")
DATA_PATHS = ("data/catalog", "data/programs")


class SealError(ValueError):
    """The sealed data cannot be made or opened (no key, wrong key, damaged file, unsafe path)."""


def new_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def parse_key(text: str) -> bytes:
    try:
        key = base64.urlsafe_b64decode(text.strip() + "=" * (-len(text.strip()) % 4))
    except (binascii.Error, ValueError) as error:
        raise SealError("ADVISOR_DATA_KEY is not a valid key") from error
    if len(key) != 32:
        raise SealError("ADVISOR_DATA_KEY is not a valid key (it must be 32 bytes, base64)")
    return key


def find_key(configured: str | None, repo_root: Path) -> bytes:
    """The key from the ADVISOR_DATA_KEY environment variable, or else from the ``.env`` file at the
    repository root: the same file Docker Compose reads, so a maintainer keeps the key in one place."""
    if configured:
        return parse_key(configured)
    env_file = repo_root / ENV_FILE
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.strip().partition("=")
            value = value.strip().strip("\"'")
            if name.strip() == "ADVISOR_DATA_KEY" and value:
                return parse_key(value)
    raise SealError(
        "The course data is sealed. Set ADVISOR_DATA_KEY in .env at the repository root (or in the "
        "environment) to open it; the project's maintainers keep the key."
    )


def read_files(root: Path, paths: tuple[str, ...] = SEALED_PATHS) -> dict[str, str]:
    """The plain files under ``paths``, by their path relative to ``root``."""
    files: dict[str, str] = {}
    for top in paths:
        folder = root / top
        if not folder.is_dir():
            raise SealError(f"{top}/ is missing; there is nothing complete to seal")
        for path in sorted(folder.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return files


def seal(files: dict[str, str], key: bytes) -> bytes:
    payload = gzip.compress(json.dumps({"format": FORMAT, "files": files}, sort_keys=True).encode("utf-8"))
    nonce = os.urandom(_NONCE)
    header = MAGIC + nonce
    return header + AESGCM(key).encrypt(nonce, payload, header)


def open_sealed(blob: bytes, key: bytes) -> dict[str, str]:
    header_length = len(MAGIC) + _NONCE
    if len(blob) <= header_length or not blob.startswith(MAGIC):
        raise SealError("This file is not sealed AUIB Academic Advisor data")
    try:
        payload = AESGCM(key).decrypt(
            blob[len(MAGIC) : header_length], blob[header_length:], blob[:header_length]
        )
    except InvalidTag as error:
        raise SealError("Wrong ADVISOR_DATA_KEY, or the sealed file has been changed or damaged") from error
    unpacker = zlib.decompressobj(wbits=31)  # gzip
    raw = unpacker.decompress(payload, MAX_UNPACKED_BYTES)
    if unpacker.unconsumed_tail:
        raise SealError("The sealed data is larger than this tool accepts")
    data = json.loads(raw)
    if data.get("format") != FORMAT or not isinstance(data.get("files"), dict):
        raise SealError("This sealed file was made by a version that this one cannot read")
    files: dict[str, str] = data["files"]
    for name in files:
        _check_path(name)
    return files


def seal_folder(root: Path, sealed: Path, key: bytes) -> int | None:
    """Seal the plain files under ``root`` into ``sealed``. Returns the number of files, or None when
    the sealed file already holds exactly these files (so it is left alone and git sees no change)."""
    files = read_files(root)
    if sealed.is_file():
        try:
            if open_sealed(sealed.read_bytes(), key) == files:
                return None
        except SealError:
            pass  # sealed with another key or damaged: write it again
    sealed.parent.mkdir(parents=True, exist_ok=True)
    sealed.write_bytes(seal(files, key))
    return len(files)


def unseal_folder(
    sealed: Path, key: bytes, root: Path, *, only: tuple[str, ...] = SEALED_PATHS, force: bool = False
) -> int:
    """Write the sealed files under ``only`` into ``root``. Plain files that differ from the sealed
    copy are not overwritten unless ``force`` is set, so unsaved edits are never lost."""
    if not sealed.is_file():
        raise SealError(f"{sealed} does not exist")
    files = {
        name: text
        for name, text in open_sealed(sealed.read_bytes(), key).items()
        if any(name.startswith(top + "/") for top in only)
    }
    changed = [
        name
        for name, text in files.items()
        if (root / name).is_file() and (root / name).read_text(encoding="utf-8") != text
    ]
    if changed and not force:
        listed = ", ".join(changed[:5]) + (f" and {len(changed) - 5} more" if len(changed) > 5 else "")
        raise SealError(
            f"These files differ from the sealed copy: {listed}. Seal them first (data-seal), or use "
            "--force to replace them with the sealed copy."
        )
    for name, text in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    return len(files)


def _check_path(name: str) -> None:
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or not any(name.startswith(top + "/") for top in SEALED_PATHS)
    ):
        raise SealError(f"The sealed file names an unsafe path: {name!r}")
