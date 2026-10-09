"""Encrypted backups of everything the database holds: the catalog and the admin records.

The database holds no student data, so a backup is the course catalog, requisite rules
(with corrections), programs and their requirement trees, term schedules, import runs,
the audit log and the catalog revision. It is written as JSON, compressed, and then
encrypted with AES-256-GCM. The key comes from the admin's passphrase through scrypt,
so the file cannot be read without the passphrase, and any change to it is detected.

File layout (all lengths in bytes):

    8   magic "AUIBBAK1"
    16  scrypt salt (n=2**15, r=8, p=1, 32-byte key)
    12  AES-GCM nonce
    ..  ciphertext followed by the 16-byte GCM tag; the 36-byte header is authenticated

Restoring replaces the tables with the backup's rows in one transaction. From the admin
page the audit log is kept (who changed what is never rolled back) and the data from just
before the restore is handed back as another encrypted backup, so a restore can be undone.
The server command (``python -m app.cli backup-restore``) restores the audit log too, for
moving to a new server. These backups complement the PostgreSQL dumps in docs/operations.md.
"""

from __future__ import annotations

import gzip
import json
import os
import zlib
from datetime import UTC, date, datetime
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from sqlalchemy import Date, DateTime, Table, delete, func, insert, inspect, select, text
from sqlalchemy.orm import Session

from app import __version__
from app.models import (
    AuditLogRow,
    CatalogStateRow,
    CourseRow,
    GroupCourseRow,
    ImportRunRow,
    ProgramRow,
    RequirementGroupRow,
    RequisiteRuleRow,
    TermOfferingRow,
    TermScheduleRow,
)

MAGIC = b"AUIBBAK1"
FORMAT = 1
MIN_PASSPHRASE_LENGTH = 12
MAX_UNPACKED_BYTES = 512 * 1024 * 1024
_SALT, _NONCE = 16, 12

# In insertion order: a table comes after every table it refers to.
TABLES: list[Table] = [
    model.__table__  # type: ignore[misc]
    for model in (
        CourseRow,
        RequisiteRuleRow,
        ProgramRow,
        RequirementGroupRow,
        GroupCourseRow,
        TermScheduleRow,
        TermOfferingRow,
        ImportRunRow,
        AuditLogRow,
        CatalogStateRow,
    )
]


class BackupError(ValueError):
    """The backup cannot be made or read (weak passphrase, wrong passphrase, damaged file)."""


def check_passphrase(passphrase: str) -> None:
    if len(passphrase) < MIN_PASSPHRASE_LENGTH:
        raise BackupError(f"Use a passphrase of at least {MIN_PASSPHRASE_LENGTH} characters")


def make_backup(session: Session, passphrase: str) -> tuple[bytes, dict[str, int]]:
    """The encrypted backup file and the number of rows per table."""
    check_passphrase(passphrase)
    data = export_data(session)
    payload = gzip.compress(json.dumps(data, separators=(",", ":")).encode("utf-8"))
    return encrypt(payload, passphrase), {name: len(rows) for name, rows in data["tables"].items()}


def read_backup(blob: bytes, passphrase: str) -> dict[str, Any]:
    payload = decrypt(blob, passphrase)
    unpacker = zlib.decompressobj(wbits=31)  # gzip
    raw = unpacker.decompress(payload, MAX_UNPACKED_BYTES)
    if unpacker.unconsumed_tail:
        raise BackupError("The backup is larger than this tool accepts")
    data: dict[str, Any] = json.loads(raw)
    if data.get("format") != FORMAT or not isinstance(data.get("tables"), dict):
        raise BackupError("This file is not a backup this version can read")
    return data


def encrypt(payload: bytes, passphrase: str) -> bytes:
    salt, nonce = os.urandom(_SALT), os.urandom(_NONCE)
    header = MAGIC + salt + nonce
    return header + AESGCM(_key(passphrase, salt)).encrypt(nonce, payload, header)


def decrypt(blob: bytes, passphrase: str) -> bytes:
    header_length = len(MAGIC) + _SALT + _NONCE
    if len(blob) <= header_length or not blob.startswith(MAGIC):
        raise BackupError("This file is not an AUIB Academic Advisor backup")
    salt = blob[len(MAGIC) : len(MAGIC) + _SALT]
    nonce = blob[len(MAGIC) + _SALT : header_length]
    try:
        return AESGCM(_key(passphrase, salt)).decrypt(nonce, blob[header_length:], blob[:header_length])
    except InvalidTag as error:
        raise BackupError("Wrong passphrase, or the file has been changed or damaged") from error


def _key(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode("utf-8"))


def export_data(session: Session) -> dict[str, Any]:
    tables = {
        table.name: [
            {column: _to_json(value) for column, value in row.items()}
            for row in session.execute(select(table).order_by(*table.primary_key.columns)).mappings()
        ]
        for table in TABLES
    }
    return {
        "format": FORMAT,
        "app_version": __version__,
        "schema_revision": _schema_revision(session),
        "created_at": datetime.now(UTC).isoformat(),
        "tables": tables,
    }


def schema_problem(session: Session, data: dict[str, Any]) -> str | None:
    """Why the backup cannot be restored into this database, or None when it can."""
    current = _schema_revision(session)
    if data.get("schema_revision") and current and data["schema_revision"] != current:
        return (
            f"The backup is from database schema {data['schema_revision']} but this database is at "
            f"{current}. Restore it with the app version that made it, then upgrade."
        )
    return None


def row_counts(session: Session) -> dict[str, int]:
    """Rows per table in the database now."""
    return {table.name: session.scalar(select(func.count()).select_from(table)) or 0 for table in TABLES}


def restore_data(session: Session, data: dict[str, Any], *, keep_audit_log: bool = False) -> dict[str, int]:
    """Replace the tables with the backup's rows. The caller commits (or rolls back).

    With ``keep_audit_log`` the audit log is left as it is (the admin page does this).
    """
    problem = schema_problem(session, data)
    if problem:
        raise BackupError(problem)
    revision_before = session.scalar(select(CatalogStateRow.revision).where(CatalogStateRow.id == 1)) or 0
    tables = data["tables"]
    restored = [table for table in TABLES if not (keep_audit_log and table.name == AuditLogRow.__tablename__)]
    for table in reversed(restored):
        session.execute(delete(table))
    counts = {}
    for table in restored:
        rows = [_from_json(table, row) for row in tables.get(table.name, [])]
        if rows:
            session.execute(insert(table), rows)
        counts[table.name] = len(rows)
    if session.get_bind().dialect.name == "postgresql":
        _reset_sequences(session)
    session.flush()
    session.expire_all()
    # Above both the old and the restored revision, so every API worker reloads the catalog.
    restored_revision = session.scalar(select(CatalogStateRow.revision).where(CatalogStateRow.id == 1)) or 0
    state = session.get(CatalogStateRow, 1)
    if state is None:
        session.add(CatalogStateRow(id=1, revision=max(revision_before, restored_revision) + 1))
    else:
        state.revision = max(revision_before, restored_revision) + 1
    session.flush()
    return counts


def _schema_revision(session: Session) -> str | None:
    """The Alembic revision of the database; None for one made without migrations (tests)."""
    if not inspect(session.connection()).has_table("alembic_version"):
        return None
    revision: str | None = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    return revision


def _reset_sequences(session: Session) -> None:
    for table in TABLES:
        column = table.columns.get("id")
        if column is None or not column.autoincrement:
            continue
        highest = session.scalar(select(func.max(column))) or 0
        session.execute(
            text("SELECT setval(pg_get_serial_sequence(:table, 'id'), :value, :called)"),
            {"table": table.name, "value": max(highest, 1), "called": highest > 0},
        )


def _to_json(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def _from_json(table: Table, row: dict[str, Any]) -> dict[str, Any]:
    values = {}
    for column in table.columns:
        if column.name not in row:
            continue
        value = row[column.name]
        if value is not None and isinstance(column.type, DateTime):
            value = datetime.fromisoformat(value)
        elif value is not None and isinstance(column.type, Date):
            value = date.fromisoformat(value)
        values[column.name] = value
    return values
